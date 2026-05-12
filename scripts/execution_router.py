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
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .approval_policy import ApprovalDecision, ApprovalPolicy, evaluate as evaluate_approval
from .journal_writer import append_safety_event
from .live_execution import LiveExecution, OrderResult
from .market_data import OrderBook
from .paper_execution import PaperFill, simulate_market_fill
from .pending_approvals import (
    PendingApproval,
    PendingApprovalsStore,
    default_deadline_iso,
    make_approval_id,
)
from .safety_state import SafetyStateManager
from .symbol_filters import SymbolSpec, is_valid_ascii_usdt_symbol

log = logging.getLogger(__name__)


VALID_MODES = ("PAPER_TRADING", "SEMI_AUTO_LIVE", "FULL_AUTO_LIVE")


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionOutcome:
    """What the router did. Caller uses ``status`` to branch.

    ``status`` values:
        'paper_filled'         — PAPER_TRADING entry simulated cleanly
        'filled'               — live entry + SL + TP all placed cleanly
        'naked_rescued'        — live entry filled BUT SL or TP failed; the
                                 router auto-issued a reduce-only MARKET
                                 close and paused safety. Caller MUST NOT
                                 persist this as an open position.
        'queued_for_approval'  — SEMI_AUTO_LIVE queued; awaiting user
        'rejected'             — never made it to the exchange
    """

    status: str
    mode: str
    proposal_id: str
    symbol: str
    side: str

    # Populated when status in ('filled', 'paper_filled', 'naked_rescued'):
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

    # Populated when status == 'rejected' OR 'naked_rescued':
    rejection_reason: str | None

    # Always populated:
    approval_decision: ApprovalDecision

    # Populated when status == 'filled' on a live entry whose SL+TP were
    # placed by the router. Map of logical role → algoId string. Empty for
    # paper / queued / rejected outcomes.
    algo_order_ids: dict[str, str] = field(default_factory=dict)

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
            "algo_order_ids": dict(self.algo_order_ids),
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
    # Optional Safety state manager — when wired, a naked-rescue path will
    # call ``safety.pause(...)``. If None, only the safety event journal
    # entry is written. Live-mode callers SHOULD wire this in.
    safety: SafetyStateManager | None = None

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
                stop_loss=stop_loss, take_profit_targets=take_profit_targets,
            )

        # 5) FULL_AUTO_LIVE — Phase 6. Fires unconditionally (the daily/consec
        # caps are still checked upstream by the Risk Manager + Safety Agent).
        if mode == "FULL_AUTO_LIVE":
            return self._fill_live(
                proposal_id=proposal_id, spec=spec, side=side, quantity=quantity,
                risk_approval_id=risk_approval_id or proposal_id,
                decision=decision,
                stop_loss=stop_loss, take_profit_targets=take_profit_targets,
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
                    stop_loss=approval.stop_loss,
                    take_profit_targets=list(approval.take_profit_targets or []),
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
        stop_loss: Decimal | None = None,
        take_profit_targets: list[Decimal] | None = None,
    ) -> ExecutionOutcome:
        assert self.live_execution is not None  # checked by caller

        # ERROR-20260511-9 defensive guard: belt-and-suspenders ASCII check
        # right before any live API call. The screener/exchangeInfo parser
        # already drops non-ASCII symbols, but we re-validate here so a
        # caller that bypassed the screener (e.g. --symbol arg) still can't
        # leak a display-name like "币安人生USDT" into newClientOrderId.
        if not is_valid_ascii_usdt_symbol(spec.symbol):
            log.warning(
                "[NON_ASCII_SYMBOL_DROPPED] router refused live fill for symbol=%r proposal=%s",
                spec.symbol, proposal_id,
            )
            return self._reject(
                proposal_id, spec.symbol, side, decision,
                reason=f"non-ASCII symbol rejected by router guard: {spec.symbol!r}",
            )

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
        filled_qty = order.executed_qty if order.executed_qty > 0 else quantity

        # --- ATOMIC BRACKET PLACEMENT ---
        # The entry just filled at MARKET. Until both SL and TP brackets are
        # on the exchange, the position is naked. We MUST either (a) place
        # both successfully and return ``filled``, or (b) immediately
        # reduce-only MARKET close the entry, pause safety, and return
        # ``naked_rescued``. There is no third option — silent partial-bracket
        # success caused 3 naked-position windows on 2026-05-11 (SAFETY-20260511-3,
        # ERROR-20260511-5). See memory/execution-errors.md.
        return self._place_brackets_or_rescue(
            proposal_id=proposal_id, spec=spec, side=side,
            entry_order=order, filled_qty=filled_qty,
            avg_price=avg, notional=notional,
            stop_loss=stop_loss,
            take_profit_targets=take_profit_targets or [],
            decision=decision,
        )

    def _place_brackets_or_rescue(
        self, *, proposal_id: str, spec: SymbolSpec, side: str,
        entry_order: OrderResult, filled_qty: Decimal,
        avg_price: Decimal | None, notional: Decimal | None,
        stop_loss: Decimal | None,
        take_profit_targets: list[Decimal],
        decision: ApprovalDecision,
    ) -> ExecutionOutcome:
        """Place SL + TP brackets atomically. Reduce-only close + pause on any failure.

        Returns:
          * ``status='filled'`` + ``algo_order_ids={'sl':..., 'tp':...}`` on full success.
          * ``status='naked_rescued'`` + rejection_reason populated when SL or TP
            placement failed AND the entry was reduce-only closed.
          * Worst case (rescue close itself fails) — ``status='naked_rescued'``
            with a CRITICAL rejection_reason; the caller MUST surface this to
            the operator immediately. Safety is paused either way.
        """
        assert self.live_execution is not None

        if stop_loss is None or not take_profit_targets:
            # Caller passed an incomplete bracket spec. Reject outright after
            # closing the entry — we never knowingly leave a position naked.
            reason = (
                "live entry filled but caller did not provide both "
                f"stop_loss ({stop_loss!r}) and take_profit_targets "
                f"({take_profit_targets!r}); cannot place brackets"
            )
            return self._rescue_naked_entry(
                proposal_id=proposal_id, spec=spec, side=side,
                entry_order=entry_order, filled_qty=filled_qty,
                avg_price=avg_price, notional=notional,
                decision=decision, reason=reason,
                bracket_results={"sl": None, "tp": None},
            )

        exit_side = "SELL" if side == "LONG" else "BUY"
        sl_result: OrderResult | None = None
        tp_result: OrderResult | None = None
        sl_error: str | None = None
        tp_error: str | None = None

        # ERROR-20260511-8: clientAlgoId must be unique across same-day retries.
        # Previous pattern f"SL-{proposal_id}" / f"TP-{proposal_id}" collided
        # when the engine retried the same symbol same-day, causing Binance
        # -4116 "ClientOrderId is duplicated". Append a 6-digit millisecond
        # suffix to guarantee uniqueness while staying within Binance's 36-char
        # cap. _build_algo_client_id handles truncation deterministically.
        sl_client_id = _build_algo_client_id("SL", proposal_id)
        tp_client_id = _build_algo_client_id("TP", proposal_id)

        # Place SL first.
        try:
            sl_result = self.live_execution.place_algo_stop_market(
                spec, side=exit_side,
                stop_price=stop_loss,
                quantity=filled_qty,
                working_type="MARK_PRICE",
                price_protect=True,
                client_order_id=sl_client_id,
            )
            if not sl_result.success:
                sl_error = sl_result.error_msg or sl_result.status or "unknown SL failure"
        except Exception as e:
            sl_error = f"{type(e).__name__}: {e}"

        # Place TP (first target only — additional targets are watcher's job).
        if sl_error is None:
            try:
                tp_target = take_profit_targets[0]
                tp_result = self.live_execution.place_algo_take_profit_market(
                    spec, side=exit_side,
                    stop_price=tp_target,
                    quantity=filled_qty,
                    working_type="MARK_PRICE",
                    price_protect=True,
                    client_order_id=tp_client_id,
                )
                if not tp_result.success:
                    tp_error = tp_result.error_msg or tp_result.status or "unknown TP failure"
            except Exception as e:
                tp_error = f"{type(e).__name__}: {e}"

        # Both succeeded — clean filled.
        if sl_error is None and tp_error is None:
            assert sl_result is not None and tp_result is not None
            algo_ids = {
                "sl": str(sl_result.order_id) if sl_result.order_id else "",
                "tp": str(tp_result.order_id) if tp_result.order_id else "",
            }
            return ExecutionOutcome(
                status="filled",
                mode="LIVE", proposal_id=proposal_id,
                symbol=spec.symbol, side=side,
                average_price=avg_price, filled_qty=filled_qty,
                notional_usdt=notional, fees_usdt=None,
                slippage_bps=None, order_id=entry_order.order_id,
                paper_fill=None, live_order=entry_order, approval=None,
                rejection_reason=None, approval_decision=decision,
                algo_order_ids=algo_ids,
            )

        # At least one bracket failed. The entry is naked — rescue it.
        bracket_results = {
            "sl": sl_result, "tp": tp_result,
        }
        reason_parts = []
        if sl_error:
            reason_parts.append(f"SL placement failed: {sl_error}")
        if tp_error:
            reason_parts.append(f"TP placement failed: {tp_error}")
        # If SL was placed but TP failed, we MUST also cancel the SL during
        # rescue so we don't leave a dangling reduce-only order against a
        # zero position (Binance keeps it but it confuses our state).
        return self._rescue_naked_entry(
            proposal_id=proposal_id, spec=spec, side=side,
            entry_order=entry_order, filled_qty=filled_qty,
            avg_price=avg_price, notional=notional,
            decision=decision, reason="; ".join(reason_parts),
            bracket_results=bracket_results,
        )

    def _rescue_naked_entry(
        self, *, proposal_id: str, spec: SymbolSpec, side: str,
        entry_order: OrderResult, filled_qty: Decimal,
        avg_price: Decimal | None, notional: Decimal | None,
        decision: ApprovalDecision, reason: str,
        bracket_results: dict[str, OrderResult | None],
    ) -> ExecutionOutcome:
        """Reduce-only MARKET close the just-filled entry + pause safety.

        ``bracket_results`` may contain a partially-placed SL or TP that we
        also need to cancel so the rescue close isn't blocked by stale algo
        orders. We try-cancel best-effort and never re-raise — the priority
        is closing the naked exposure.
        """
        assert self.live_execution is not None

        # Best-effort cancel any partially-placed bracket.
        for role, br in bracket_results.items():
            if br is None or not br.success or br.order_id is None:
                continue
            try:
                self.live_execution.cancel_algo_order(spec.symbol, algo_id=br.order_id)
                log.warning(
                    "naked-rescue cancelled stale %s algoId %s for %s",
                    role, br.order_id, spec.symbol,
                )
            except Exception as e:
                log.error(
                    "naked-rescue: failed to cancel stale %s algoId %s for %s: %r",
                    role, br.order_id, spec.symbol, e,
                )

        # Issue the reduce-only MARKET close.
        close_error: str | None = None
        close_result: OrderResult | None = None
        try:
            close_result = self.live_execution.close_position_market(
                spec, position_side=side, quantity=filled_qty,
                client_order_id=f"NAKEDFIX-{proposal_id}"[:36],
            )
            if not close_result.success:
                close_error = close_result.error_msg or close_result.status or "unknown close failure"
        except Exception as e:
            close_error = f"{type(e).__name__}: {e}"

        # Pause safety + journal a high-severity event regardless of outcome.
        pause_reason = (
            f"naked_entry_rescue {spec.symbol}/{side} proposal={proposal_id} "
            f"reason={reason}"
        )
        if self.safety is not None:
            try:
                self.safety.pause(pause_reason, carry_over_rollover=True)
            except Exception as e:
                log.error("naked-rescue: safety.pause failed: %r", e)

        event_id = f"SAFETY-NAKED-{_now_compact()}-{spec.symbol}"
        try:
            append_safety_event({
                "event_id": event_id,
                "timestamp": _now_iso(),
                "mode": "LIVE",
                "event_type": "naked_entry_rescue",
                "triggered_by": "execution-router",
                "details": (
                    f"symbol={spec.symbol} side={side} proposal_id={proposal_id} "
                    f"entry_order_id={entry_order.order_id} filled_qty={filled_qty}; "
                    f"{reason}"
                ),
                "positions_affected": [proposal_id],
                "action_taken": (
                    "reduce-only MARKET close issued"
                    + (f" (close_order_id={close_result.order_id})" if close_result and close_result.order_id else "")
                    + (f" — CLOSE FAILED: {close_error}" if close_error else " — close succeeded")
                ),
                "duration_minutes": 0,
                "resolved_at": _now_iso() if not close_error else "",
                "resolution_notes": (
                    "safety paused (carry_over_rollover=true); "
                    "operator must verify exchange flat before resume"
                ),
            })
        except Exception as e:
            log.error("naked-rescue: append_safety_event failed: %r", e)

        rescue_reason = (
            f"NAKED_RESCUED entry order_id={entry_order.order_id} filled_qty={filled_qty}; "
            f"{reason}; "
            + ("close ok" if not close_error else f"CLOSE FAILED: {close_error} — MANUAL INTERVENTION REQUIRED")
        )
        return ExecutionOutcome(
            status="naked_rescued",
            mode="LIVE", proposal_id=proposal_id,
            symbol=spec.symbol, side=side,
            average_price=avg_price, filled_qty=filled_qty,
            notional_usdt=notional, fees_usdt=None,
            slippage_bps=None, order_id=entry_order.order_id,
            paper_fill=None, live_order=entry_order, approval=None,
            rejection_reason=rescue_reason, approval_decision=decision,
            algo_order_ids={},
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


def _now_compact() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")


# Binance clientAlgoId hard limit (per /fapi/v1/algoOrder docs).
_BINANCE_CLIENT_ID_MAX_LEN = 36


def _build_algo_client_id(role: str, proposal_id: str) -> str:
    """Construct a unique clientAlgoId of the form ``<ROLE>-<proposal>-<ms6>``.

    ERROR-20260511-8: the previous fixed pattern collided when the same
    proposal symbol was retried in the same UTC day. The 6-digit millisecond
    suffix (``int(time.time()*1000) % 1_000_000``) guarantees retries differ
    while staying under Binance's 36-char limit. If the prefix+proposal_id
    would push us over the cap, the proposal_id is truncated — the suffix is
    always preserved because that's what makes the id unique.
    """
    suffix = f"{int(time.time() * 1000) % 1_000_000:06d}"
    # 3 dashes (after role, after proposal trunc, before suffix) — actually 2:
    # ``<role>-<proposal>-<suffix>``
    overhead = len(role) + 1 + 1 + len(suffix)  # role + '-' + '-' + suffix
    proposal_budget = _BINANCE_CLIENT_ID_MAX_LEN - overhead
    if proposal_budget < 1:
        # Pathologically long role; degrade gracefully to role+suffix only.
        return f"{role}-{suffix}"[:_BINANCE_CLIENT_ID_MAX_LEN]
    truncated_proposal = proposal_id[:proposal_budget]
    return f"{role}-{truncated_proposal}-{suffix}"


__all__ = [
    "ExecutionOutcome",
    "ExecutionRouter",
    "VALID_MODES",
]
