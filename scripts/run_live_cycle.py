"""SEMI_AUTO_LIVE entrypoint.

Same scan / research / strategy / risk pipeline as ``run_paper_cycle.py``,
but every approved proposal goes through ``execution_router`` instead of
``paper_execution`` directly.

Routing rule (configurable via --approval-threshold):

    notional ≤ $50  → auto-fire through live_execution
    notional >  $50 → queue for explicit user approval (run_approvals.py)

Plus defensive gates from ``approval_policy.py``:
  - First live trade of session always asks
  - Daily loss ≥ 75% of limit always asks
  - Leverage > 5x flagged in journal (does not by itself ask)

Safety preconditions enforced before any signed call:
  - User passed ``--i-understand-this-is-real-money``
  - ``BINANCE_API_KEY`` + ``BINANCE_API_SECRET`` env vars set
  - Permission preflight passes (no withdrawal permission on the key)
  - Safety Agent's health check is green (no daily-loss / consecutive-loss pause)

Default base URL is testnet; mainnet requires ``BINANCE_LIVE=true`` env.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from .account import Account
from .approval_policy import ApprovalPolicy
from .binance_client import BinanceClient
from .binance_signed_client import (
    SignedClient,
    SignedRequestsDisabledError,
)
from .execution_router import ExecutionRouter
from .health_check import run_health_check
from .journal_writer import (
    append_rejection, make_proposal_id, make_rejection_id,
)
from .limits import check_proposal
from .live_execution import LiveExecution
from .market_data import MarketData
from .pending_approvals import PendingApprovalsStore
from .position_manager import reconcile_via_apis
from .positions_store import Position, PositionsStore, make_position_id
from .risk_engine import RiskConfig, evaluate_proposal
from .safety_state import SafetyLimits, SafetyStateManager
from .strategy_scoring import rank_strategies
from .symbol_filters import parse_exchange_info, round_price
from .token_research import research_token
from .token_screener import ScreeningConfig, run_screener


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENCY_STATE = _PROJECT_ROOT / "data" / "agency-state.json"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run one SEMI_AUTO_LIVE cycle")
    p.add_argument(
        "--i-understand-this-is-real-money", action="store_true",
        help="confirm you want to send live (or testnet) orders. Required.",
    )
    p.add_argument(
        "--approval-threshold", type=str, default="50",
        help="notional USDT above which user approval is required (default 50)",
    )
    p.add_argument("--top", type=int, default=3,
                   help="research the top N screened candidates")
    p.add_argument("--symbol", help="bypass screener and research a single symbol")
    p.add_argument("--min-quote-volume", type=str, default="5000000")
    p.add_argument("--margin-usdt", type=str, default="2",
                   help="default margin per trade USDT (capped to risk_engine max)")
    p.add_argument("--leverage", type=int, default=3)
    p.add_argument("--max-loss-pct", type=str, default="0.08",
                   help="max planned loss as fraction of margin (default 0.08 = 8%)")
    p.add_argument("--skip-permission-check", action="store_true",
                   help="(testnet only) skip the withdrawal-permission probe")
    p.add_argument("--reconcile-first", action="store_true",
                   help="run a position-manager reconcile before placing orders")
    p.add_argument("--no-execute-queue", action="store_true",
                   help="don't try to fire previously-approved queued items this cycle")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if not args.i_understand_this_is_real_money:
        print(json.dumps({
            "error": "refusing to run without --i-understand-this-is-real-money",
            "explanation": (
                "SEMI_AUTO_LIVE places real Binance Futures orders. Default base URL "
                "is testnet — set BINANCE_LIVE=true for mainnet. Either way, you "
                "have to confirm you know what's about to happen."
            ),
        }, indent=2))
        return 2

    cycle_started = dt.datetime.utcnow()
    report: dict[str, Any] = {
        "workflow_status": "running",
        "mode": "SEMI_AUTO_LIVE",
        "started_at": cycle_started.isoformat(timespec="seconds") + "Z",
        "warnings": [],
    }

    # ---- 1) Public market data client + safety + auth ----
    public_client = BinanceClient()
    market = MarketData(public_client)

    health = run_health_check(public_client)
    report["safety"] = health.to_jsonable()
    if not health.trading_allowed:
        report["workflow_status"] = "halted"
        report["next_actions"] = ["resolve safety warnings before running again"]
        _emit(report)
        return 0

    # SafetyState: rollover + can-trade gate (Phase 6 caps apply to SEMI_AUTO too).
    safety = SafetyStateManager()
    state, did_rollover = safety.perform_daily_rollover_if_needed()
    if did_rollover:
        report["warnings"].append("daily rollover performed (new UTC day)")
    state, can_trade, why = safety.check_can_trade(force_rollover_check=False)
    report["safety_state"] = state.to_jsonable()
    report["safety_state"]["can_trade"] = can_trade
    report["safety_state"]["reason"] = why
    if not can_trade:
        report["workflow_status"] = "halted"
        report["next_actions"] = [
            f"safety state blocks trading: {why}",
            "use `python -m scripts.run_safety_reset --resume` after verifying it's safe",
        ]
        _emit(report)
        return 0

    signed_client = SignedClient()
    signed_client.enable_signed_requests()
    account = Account(signed_client)

    if not args.skip_permission_check:
        perms = account.check_permissions()
        report["permissions"] = {
            "trading_enabled": perms.trading_enabled,
            "withdrawals_enabled": perms.withdrawals_enabled,
            "futures_enabled": perms.futures_enabled,
            "ip_restrict": perms.ip_restrict,
            "is_safe_to_trade": perms.is_safe_to_trade,
            "notes": list(perms.notes),
        }
        if not perms.is_safe_to_trade:
            report["workflow_status"] = "halted"
            report["next_actions"] = [
                "permission preflight failed — see report.permissions for details",
            ]
            _emit(report)
            return 1

    # ---- 2) Optional reconcile first ----
    if args.reconcile_first:
        try:
            recon = reconcile_via_apis(account=account)
            report["reconciliation"] = recon.to_jsonable()
            if not recon.is_clean:
                report["warnings"].append(
                    f"reconciliation found {len(recon.mismatches)} mismatch(es) — "
                    "investigate before opening new positions"
                )
                report["workflow_status"] = "halted"
                _emit(report)
                return 1
        except Exception as e:
            report["warnings"].append(f"reconciliation failed: {e!r}")

    # ---- 3) Build router ----
    live_exec = LiveExecution(signed_client)
    router = ExecutionRouter(
        live_execution=live_exec,
        approval_policy=ApprovalPolicy(notional_threshold_usdt=Decimal(args.approval_threshold)),
        approvals_store=PendingApprovalsStore(),
    )

    # ---- 4) Fire any previously-approved queue items first ----
    queued_outcomes: list[dict[str, Any]] = []
    if not args.no_execute_queue:
        info = market.get_exchange_info()
        spec_lookup = parse_exchange_info(info)
        outcomes = router.execute_approved_queue(spec_lookup=spec_lookup)
        queued_outcomes = [o.to_jsonable() for o in outcomes]
    report["executed_from_queue"] = queued_outcomes

    # ---- 5) Screen + research + decide ----
    if args.symbol:
        info = market.get_exchange_info()
        specs = parse_exchange_info(info)
        if args.symbol not in specs:
            report["workflow_status"] = "halted"
            report["warnings"].append(f"unknown symbol {args.symbol}")
            _emit(report)
            return 1
        spec = specs[args.symbol]
        ticker = market.get_ticker_24h(args.symbol)
        candidates_for_research = [(spec, ticker)]
        report["screener"] = {"skipped": True, "reason": f"--symbol={args.symbol}"}
    else:
        cfg = ScreeningConfig(
            min_24h_quote_volume_usdt=Decimal(args.min_quote_volume),
            max_candidates=max(args.top, 5),
        )
        screening = run_screener(market, cfg)
        report["screener"] = screening.to_jsonable()
        if not screening.candidates:
            report["workflow_status"] = "no_candidates"
            _emit(report)
            return 0
        info = market.get_exchange_info()
        specs = parse_exchange_info(info)
        candidates_for_research = []
        for c in screening.candidates[: args.top]:
            spec = specs.get(c.symbol)
            if spec is None:
                continue
            ticker = market.get_ticker_24h(c.symbol)
            candidates_for_research.append((spec, ticker))

    risk_cfg = RiskConfig(
        default_margin_per_trade_usdt=Decimal(args.margin_usdt),
        max_margin_per_trade_usdt=Decimal(args.margin_usdt),
        default_leverage=args.leverage,
        max_leverage=max(args.leverage, 5),
        max_planned_loss_pct_of_margin=Decimal(args.max_loss_pct),
    )

    routed_outcomes: list[dict[str, Any]] = []
    opened_positions: list[dict[str, Any]] = []
    fired_this_cycle = 0
    sm_limits = SafetyLimits()  # Phase 6 caps default — same defaults SEMI honors

    for spec, ticker in candidates_for_research:
        # Pre-trade limits: re-check between proposals.
        state, can_trade, _why = safety.check_can_trade(force_rollover_check=False)
        if not can_trade:
            report["warnings"].append(f"mid-cycle safety stop: {_why}")
            break
        lc = check_proposal(
            state=state, limits=sm_limits, proposed_symbol=spec.symbol,
            open_positions=PositionsStore().load_open(),
            fired_this_cycle=fired_this_cycle,
        )
        if not lc.ok:
            hard = {"paused", "daily_loss_limit", "consecutive_loss_limit",
                    "per_cycle_trade_cap"}
            if any(b in hard for b in lc.breached):
                report["warnings"].append(
                    f"limits cap reached: {', '.join(lc.reasons)}"
                )
                break
            routed_outcomes.append({
                "symbol": spec.symbol, "status": "limits_skipped",
                "reasons": list(lc.reasons),
            })
            continue

        try:
            research = research_token(market, spec, ticker_24h=ticker)
        except Exception as e:
            report["warnings"].append(f"research failed for {spec.symbol}: {e!r}")
            continue
        ranking = rank_strategies(research)
        if ranking.best is None:
            continue

        best = ranking.best
        if not best.entry_zone or best.invalidation is None or not best.take_profit_targets:
            continue

        entry_mid = (best.entry_zone[0] + best.entry_zone[1]) / Decimal("2")
        entry = round_price(spec, entry_mid, mode="down")
        stop = round_price(spec, best.invalidation,
                           mode="down" if best.side == "LONG" else "up")
        tp1 = round_price(spec, best.take_profit_targets[0],
                          mode="down" if best.side == "LONG" else "up")

        proposal_id = make_proposal_id(spec.symbol, seq=len(routed_outcomes) + 1)
        approval = evaluate_proposal(
            proposal_id=proposal_id, spec=spec, side=best.side,
            entry_price=entry, stop_price=stop, take_profit_price=tp1,
            cfg=risk_cfg,
        )
        if approval.risk_decision != "approved" or approval.sizing is None:
            append_rejection({
                "rejection_id": make_rejection_id(seq=len(routed_outcomes) + 1),
                "proposal_id": proposal_id,
                "mode": "SEMI_AUTO_LIVE", "symbol": spec.symbol,
                "side": best.side, "strategy": best.strategy,
                "proposed_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "rejected_by": "risk-manager",
                "rejection_reason": approval.risk_reason,
                "market_regime": "unknown",
                "hindsight_outcome": "unclear", "hindsight_notes": "",
            })
            routed_outcomes.append({
                "symbol": spec.symbol, "proposal_id": proposal_id,
                "status": "risk_rejected", "reason": approval.risk_reason,
            })
            continue

        sizing = approval.sizing
        # If live leverage is set per-symbol; idempotent error codes are OK.
        try:
            live_exec.set_leverage(spec.symbol, sizing.leverage)
        except Exception as e:
            report["warnings"].append(f"set_leverage {spec.symbol} failed: {e!r}")

        outcome = router.route(
            mode="SEMI_AUTO_LIVE",
            proposal_id=proposal_id,
            spec=spec, side=best.side,
            quantity=sizing.quantity, entry_price=entry,
            stop_loss=stop,
            take_profit_targets=[round_price(spec, t,
                                             mode="down" if best.side == "LONG" else "up")
                                 for t in best.take_profit_targets],
            leverage=sizing.leverage, margin_mode="ISOLATED",
            margin_usdt=sizing.margin_usdt,
            estimated_fees_usdt=sizing.estimated_fees_usdt,
            liquidation_price=approval.liquidation.liquidation_price if approval.liquidation else None,
            strategy=best.strategy,
            risk_approval_id=proposal_id,
        )
        routed_outcomes.append(outcome.to_jsonable())

        # If filled live, persist as a tracked Position so the watcher takes it.
        if outcome.status == "filled" and outcome.live_order is not None:
            position = Position(
                position_id=make_position_id(spec.symbol, seq=len(opened_positions) + 1),
                symbol=spec.symbol, side=best.side, status="open",
                entry_price=outcome.average_price or entry,
                quantity=outcome.filled_qty or sizing.quantity,
                initial_quantity=outcome.filled_qty or sizing.quantity,
                leverage=sizing.leverage, margin_mode="ISOLATED",
                margin_usdt=sizing.margin_usdt,
                notional_usdt=outcome.notional_usdt or sizing.notional_usdt,
                stop_loss=stop,
                take_profit_targets=[round_price(spec, t,
                                                 mode="down" if best.side == "LONG" else "up")
                                     for t in best.take_profit_targets],
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                max_favorable_pnl=Decimal("0"),
                max_adverse_pnl=Decimal("0"),
                liquidation_price=approval.liquidation.liquidation_price if approval.liquidation else None,
                fees_paid_usdt=Decimal("0"),
                funding_paid_usdt=Decimal("0"),
                proposal_id=proposal_id, strategy=best.strategy,
                market_regime="live",
                opened_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                updated_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                closed_at=None, exit_price=None, exit_reason=None,
                mode="SEMI_AUTO_LIVE",
                order_ids=[str(outcome.order_id)] if outcome.order_id else [],
                notes=[outcome.approval_decision.reason],
            )
            PositionsStore().upsert(position)
            opened_positions.append({
                "position_id": position.position_id, "symbol": spec.symbol,
                "side": best.side, "strategy": best.strategy,
                "entry_price": str(position.entry_price),
                "quantity": str(position.quantity),
                "stop_loss": str(stop),
                "take_profit_targets": [str(t) for t in position.take_profit_targets],
                "order_id": outcome.order_id,
            })
            fired_this_cycle += 1

    report["routed_outcomes"] = routed_outcomes
    report["opened_positions"] = opened_positions

    queued = [r for r in routed_outcomes if r.get("status") == "queued_for_approval"]
    filled = [r for r in routed_outcomes if r.get("status") == "filled"]
    rejected = [r for r in routed_outcomes if r.get("status") == "rejected"]

    report["summary"] = {
        "candidates_screened": len(report.get("screener", {}).get("candidates", []))
                                if "candidates" in report.get("screener", {}) else 1,
        "approved_proposals": len(filled) + len(queued),
        "auto_filled": len(filled),
        "queued_for_approval": len(queued),
        "rejected": len(rejected),
        "executed_from_queue_count": len(queued_outcomes),
    }
    next_actions: list[str] = []
    if queued:
        next_actions.append(
            f"Run `python -m scripts.run_approvals --inline` to review "
            f"{len(queued)} queued trade(s)."
        )
    if filled:
        next_actions.append(
            "Run `python -m scripts.run_watch_positions --loop` to manage open live positions."
        )
    if next_actions:
        report["next_actions"] = next_actions

    report["workflow_status"] = "complete"
    report["finished_at"] = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    _emit(report)
    return 0


def _emit(report: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(report, indent=2, default=str))
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
