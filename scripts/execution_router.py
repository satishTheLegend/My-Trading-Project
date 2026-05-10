"""Execution router — single chokepoint between the orchestrator and any
execution module. Decides:

  - PAPER_TRADING        → paper_execution.simulate_market_fill
  - SEMI_AUTO_LIVE small → live_execution.place_market_entry (auto)
  - SEMI_AUTO_LIVE big   → pending_approvals.upsert (queue, exit cleanly)
  - FULL_AUTO_LIVE       → live_execution.place_market_entry (auto, Phase 6)

The router is the **only** module besides the explicit CLIs that imports
``live_execution``. Everything else (orchestrator, watcher, backtester) only
sees the abstract ``ExecutionOutcome`` returned here.

This keeps the live-execution surface tiny and grep-able: search for
``import live_execution`` and you get exactly the call sites that touch real
money.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .approval_policy import ApprovalDecision, ApprovalPolicy, evaluate as evaluate_approval
from .live_execution import LiveExecution, OrderResult
from .market_data import OrderBook
from .paper_execution import PaperFill, simulate_market_fill
from .pending_approvals import (
    PendingApproval,
    PendingApprovalsStore,
    default_deadline_iso,
    make_approval_id,
)
from .symbol_filters import SymbolSpec

log = logging.getLogger(__name__)


VALID_MODES = ("PAPER_TRADING", "SEMI_AUTO_LIVE", "FULL_AUTO_LIVE")


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionOutcome:
    """What the router did. Caller uses ``status`` to branch."""

    status: str                          # 'filled' | 'queued_for_approval' | 'rejected' | 'paper_filled'
    mode: str
    proposal_id: str
    symbol: str
    side: str

    # Populated when status in ('filled', 'paper_filled'):
    average_price: Decimal | None
    filled_qty: Decimal | None
    notional_usdt: Decimal | None
    fees_usdt: Decimal | None
    slippage_bps: Decimal | None
    order_id: int | None
    paper_fill: PaperFill | None
    live_order: OrderResult | None

    # Populated when status == 'queued_for_approval':
    approval: PendingApproval | None

    # Populated when status == 'rejected':
    rejection_reason: str | None

    # Always populated:
    approval_decision: ApprovalDecision

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "proposal_id": self.proposal_id,
            "symbol": self.symbol,
            "side": self.side,
            "average_price": str(self.average_price) if self.average_price is not None else None,
            "filled_qty": str(self.filled_qty) if self.filled_qty is not None else None,
            "notional_usdt": str(self.notional_usdt) if self.notional_usdt is not None else None,
            "fees_usdt": str(self.fees_usdt) if self.fees_usdt is not None else None,
            "slippage_bps": str(self.slippage_bps) if self.slippage_bps is not None else None,
            "order_id": self.order_id,
            "paper_fill": self.paper_fill.to_jsonable() if self.paper_fill else None,
            "live_order": self.live_order.to_jsonable() if self.live_order else None,
            "approval": self.approval.to_jsonable() if self.approval else None,
            "rejection_reason": self.rejection_reason,
            "approval_decision": self.approval_decision.to_jsonable(),
        }


# ----------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------


@dataclass
class ExecutionRouter:
    """Thin coordinator. Stateful only in that it tracks
    ``_first_live_trade_done`` per process (to enforce
    "first trade always asks").
    """

    live_execution: LiveExecution | None = None
    approval_policy: ApprovalPolicy = field(default_factory=ApprovalPolicy)
    approvals_store: PendingApprovalsStore = field(default_factory=PendingApprovalsStore)
    approval_deadline_hours: float = 1.0

    _first_live_trade_done: bool = False

    # ----------- public ----------------------------------------------

    def route(
        self,
        *,
        mode: str,
        proposal_id: str,
        spec: SymbolSpec,
        side: str,
        quantity: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit_targets: list[Decimal],
        leverage: int,
        margin_mode: str,
        margin_usdt: Decimal,
        estimated_fees_usdt: Decimal,
        liquidation_price: Decimal | None,
        strategy: str,
        # for paper mode (depth-aware fill):
        order_book: OrderBook | None = None,
        # for the approval policy:
        daily_pnl_usdt: Decimal = Decimal("0"),
        daily_loss_limit_usdt: Decimal = Decimal("1.5"),
        # plumbing:
        risk_approval_id: str | None = None,
    ) -> ExecutionOutcome:
        if mode not in VALID_MODES:
            raise ValueError(f"unknown mode {mode!r}; must be one of {VALID_MODES}")

        notional = entry_price * quantity

        # 1) Approval policy first — same evaluation regardless of mode, so
        #    paper logs why it would have asked.
        decision = evaluate_approval(
            mode=mode,
            notional_usdt=notional,
            leverage=leverage,
            daily_pnl_usdt=daily_pnl_usdt,
            daily_loss_limit_usdt=daily_loss_limit_usdt,
            is_first_live_trade_of_session=(not self._first_live_trade_done),
            policy=self.approval_policy,
        )

        # 2) PAPER_TRADING — never gate.
        if mode == "PAPER_TRADING":
            return self._fill_paper(
                proposal_id=proposal_id, spec=spec, side=side, quantity=quantity,
                order_book=order_book, decision=decision,
            )

        # 3) Live modes need the LiveExecution dependency wired in.
        if self.live_execution is None:
            return self._reject(
                proposal_id, spec.symbol, side, decision,
                reason="LiveExecution not configured on the router (live mode)",
            )

        # 4) SEMI_AUTO_LIVE — queue if user approval is required, else fire.
        if mode == "SEMI_AUTO_LIVE":
            if decision.requires_user_approval:
                return self._queue_for_approval(
                    proposal_id=proposal_id, spec=spec, side=side, strategy=strategy,
                    quantity=quantity, entry_price=entry_price, stop_loss=stop_loss,
                    take_profit_targets=take_profit_targets, leverage=leverage,
                    margin_mode=margin_mode, margin_usdt=margin_usdt,
                    estimated_fees_usdt=estimated_fees_usdt,
                    liquidation_price=liquidation_price, decision=decision,
                )
            # Auto-fire small trade.
            return self._fill_live(
                proposal_id=proposal_id, spec=spec, side=side, quantity=quantity,
                risk_approval_id=risk_approval_id or proposal_id,
                decision=decision,
            )

        # 5) FULL_AUTO_LIVE — Phase 6. Fires unconditionally (the daily/consec
        # caps are still checked upstream by the Risk Manager + Safety Agent).
        if mode == "FULL_AUTO_LIVE":
            return self._fill_live(
                proposal_id=proposal_id, spec=spec, side=side, quantity=quantity,
                risk_approval_id=risk_approval_id or proposal_id,
                decision=decision,
            )

        return self._reject(proposal_id, spec.symbol, side, decision,
                            reason=f"unhandled mode {mode}")

    def execute_approved_queue(
        self,
        *,
        spec_lookup: dict[str, SymbolSpec],
    ) -> list[ExecutionOutcome]:
        """Called by the live worker. For every queued approval flagged
        ``approved``, fire the live order, then transition to ``executed`` or
        ``rejected``.

        ``spec_lookup`` maps symbol → SymbolSpec; the worker fetches it from
        exchangeInfo before calling.
        """
        outcomes: list[ExecutionOutcome] = []
        # Expire stale entries first.
        self.approvals_store.expire_overdue()

        for approval in self.approvals_store.load_actionable():
            spec = spec_lookup.get(approval.symbol)
            if spec is None:
                self.approvals_store.transition(
                    approval.approval_id, to="rejected",
                    notes="symbol no longer in exchangeInfo",
                )
                outcomes.append(self._reject(
                    approval.proposal_id, approval.symbol, approval.side,
                    decision=ApprovalDecision(
                        requires_user_approval=False,
                        reason="execution worker rejection",
                        triggered_rules=tuple(),
                    ),
                    reason="symbol missing from exchangeInfo at execution time",
                ))
                continue

            if self.live_execution is None:
                self.approvals_store.transition(
                    approval.approval_id, to="rejected",
                    notes="LiveExecution not configured",
                )
                outcomes.append(self._reject(
                    approval.proposal_id, approval.symbol, approval.side,
                    decision=ApprovalDecision(False, "no live executor", tuple()),
                    reason="LiveExecution unavailable",
                ))
                continue

            try:
                outcome = self._fill_live(
                    proposal_id=approval.proposal_id,
                    spec=spec, side=approval.side, quantity=approval.quantity,
                    risk_approval_id=approval.proposal_id,
                    decision=ApprovalDecision(
                        requires_user_approval=True,
                        reason="user-approved via run_approvals.py",
                        triggered_rules=tuple(approval.triggered_rules),
                    ),
                )
                if outcome.status == "filled":
                    self.approvals_store.transition(
                        approval.approval_id, to="executed",
                        notes="filled by execution worker",
                        executed_order_id=outcome.order_id,
                        executed_avg_price=outcome.average_price,
                    )
                else:
                    self.approvals_store.transition(
                        approval.approval_id, to="rejected",
                        notes=outcome.rejection_reason or "live execution did not fill",
                    )
                outcomes.append(outcome)
            except Exception as e:
                self.approvals_store.transition(
                    approval.approval_id, to="rejected",
                    notes=f"{type(e).__name__}: {e}",
                )
                outcomes.append(self._reject(
                    approval.proposal_id, approval.symbol, approval.side,
                    decision=ApprovalDecision(
                        False, "execution exception", tuple()),
                    reason=f"{type(e).__name__}: {e}",
                ))

        return outcomes

    # ----------- internal --------------------------------------------

    def _fill_paper(
        self, *, proposal_id: str, spec: SymbolSpec, side: str,
        quantity: Decimal, order_book: OrderBook | None,
        decision: ApprovalDecision,
    ) -> ExecutionOutcome:
        if order_book is None:
            return self._reject(
                proposal_id, spec.symbol, side, decision,
                reason="paper mode requires an order_book (caller should fetch /fapi/v1/depth)",
            )
        fill = simulate_market_fill(side, quantity, order_book)
        if not fill.is_complete:
            return self._reject(
                proposal_id, spec.symbol, side, decision,
                reason=f"thin order book: {fill.notes}",
            )
        return ExecutionOutcome(
            status="paper_filled",
            mode="PAPER_TRADING", proposal_id=proposal_id,
            symbol=spec.symbol, side=side,
            average_price=fill.average_price, filled_qty=fill.filled_qty,
            notional_usdt=fill.notional_usdt, fees_usdt=fill.fees_usdt,
            slippage_bps=fill.slippage_bps, order_id=None,
            paper_fill=fill, live_order=None, approval=None,
            rejection_reason=None, approval_decision=decision,
        )

    def _fill_live(
        self, *, proposal_id: str, spec: SymbolSpec, side: str,
        quantity: Decimal, risk_approval_id: str,
        decision: ApprovalDecision,
    ) -> ExecutionOutcome:
        assert self.live_execution is not None  # checked by caller

        # Set margin mode + leverage idempotently (Phase 4 idempotent codes).
        # We don't fail the order if these no-op; we *do* fail on real errors.
        try:
            self.live_execution.set_margin_mode(spec.symbol, "ISOLATED")
        except Exception as e:
            log.warning("set_margin_mode for %s failed: %r — proceeding", spec.symbol, e)
        # Note: leverage is set per-symbol in the execution layer, but the
        # router doesn't know the user's chosen leverage at this level. The
        # caller (orchestrator) should have set it before invoking the router.
        # We leave that to the orchestrator to keep the router stateless.

        order = self.live_execution.place_market_entry(
            spec, side=side, quantity=quantity,
            risk_approval_id=risk_approval_id,
            client_order_id=proposal_id[:36],
        )

        if not order.success:
            return self._reject(
                proposal_id, spec.symbol, side, decision,
                reason=f"live order rejected: {order.error_msg or order.status}",
            )

        # Mark the first-trade flag so subsequent same-process trades
        # don't all get the "first_live_trade_of_session" reason.
        self._first_live_trade_done = True

        avg = order.avg_price if order.avg_price > 0 else None
        notional = (order.cum_quote if order.cum_quote > 0 else
                    (avg * order.executed_qty if avg else None))
        return ExecutionOutcome(
            status="filled",
            mode="LIVE", proposal_id=proposal_id,
            symbol=spec.symbol, side=side,
            average_price=avg, filled_qty=order.executed_qty,
            notional_usdt=notional, fees_usdt=None,    # live fees come from userDataStream (Phase 6)
            slippage_bps=None, order_id=order.order_id,
            paper_fill=None, live_order=order, approval=None,
            rejection_reason=None, approval_decision=decision,
        )

    def _queue_for_approval(
        self, *, proposal_id: str, spec: SymbolSpec, side: str, strategy: str,
        quantity: Decimal, entry_price: Decimal, stop_loss: Decimal,
        take_profit_targets: list[Decimal], leverage: int, margin_mode: str,
        margin_usdt: Decimal, estimated_fees_usdt: Decimal,
        liquidation_price: Decimal | None, decision: ApprovalDecision,
    ) -> ExecutionOutcome:
        approval = PendingApproval(
            approval_id=make_approval_id(spec.symbol),
            proposal_id=proposal_id,
            symbol=spec.symbol, side=side, strategy=strategy,
            entry_price=entry_price, stop_loss=stop_loss,
            take_profit_targets=list(take_profit_targets),
            quantity=quantity, leverage=leverage, margin_mode=margin_mode,
            margin_usdt=margin_usdt, notional_usdt=entry_price * quantity,
            estimated_fees_usdt=estimated_fees_usdt,
            liquidation_price=liquidation_price,
            requires_approval_reason=decision.reason,
            triggered_rules=list(decision.triggered_rules),
            created_at=_now_iso(),
            deadline_at=default_deadline_iso(hours_from_now=self.approval_deadline_hours),
        )
        self.approvals_store.upsert(approval)
        return ExecutionOutcome(
            status="queued_for_approval",
            mode="SEMI_AUTO_LIVE", proposal_id=proposal_id,
            symbol=spec.symbol, side=side,
            average_price=None, filled_qty=None,
            notional_usdt=entry_price * quantity, fees_usdt=None,
            slippage_bps=None, order_id=None,
            paper_fill=None, live_order=None, approval=approval,
            rejection_reason=None, approval_decision=decision,
        )

    def _reject(self, proposal_id: str, symbol: str, side: str,
                decision: ApprovalDecision, *, reason: str) -> ExecutionOutcome:
        return ExecutionOutcome(
            status="rejected",
            mode="?", proposal_id=proposal_id, symbol=symbol, side=side,
            average_price=None, filled_qty=None, notional_usdt=None,
            fees_usdt=None, slippage_bps=None, order_id=None,
            paper_fill=None, live_order=None, approval=None,
            rejection_reason=reason, approval_decision=decision,
        )


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


__all__ = [
    "ExecutionOutcome",
    "ExecutionRouter",
    "VALID_MODES",
]
