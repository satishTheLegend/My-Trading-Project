"""FULL_AUTO_LIVE entrypoint — Phase 6.

Same scan / research / risk pipeline as the live cycle, but every Risk
Manager-approved + Safety Agent-cleared proposal fires automatically through
``execution_router`` with ``mode=FULL_AUTO_LIVE``. Strict caps are enforced
between proposals via ``limits.check_proposal``, so a mid-cycle breach
(e.g., a fill that loses big enough to trip the daily-loss cap) stops
further trades immediately.

Mandatory flags / env:
  --i-understand-this-fires-trades-without-asking
  BINANCE_API_KEY, BINANCE_API_SECRET     (env vars only — never on CLI)
  BINANCE_LIVE=true   (opt-in to mainnet; default is testnet)

Strict caps applied before every proposal:
  - paused (any reason)        → cycle aborts
  - daily_loss_limit           → cycle aborts (already paused by watcher anyway)
  - consecutive_loss_limit     → cycle aborts (cooldown set, see safety_state)
  - max_open_positions         → skip this proposal, try the next
  - no_duplicate_symbol        → skip this proposal, try the next
  - per_cycle_trade_cap        → cycle stops firing further trades

Daily rollover happens automatically at the start of every cycle (UTC
midnight boundary). Manual reset: ``python -m scripts.run_safety_reset
--reset-daily``.
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
    append_rejection, append_safety_event, make_proposal_id, make_rejection_id,
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
    p = argparse.ArgumentParser(description="Run one FULL_AUTO_LIVE cycle")
    p.add_argument(
        "--i-understand-this-fires-trades-without-asking",
        action="store_true",
        help="confirm you want fully-automatic live trading. Required.",
    )
    p.add_argument("--top", type=int, default=3)
    p.add_argument("--symbol", help="bypass screener and try a single symbol")
    p.add_argument("--min-quote-volume", type=str, default="5000000")
    p.add_argument("--margin-usdt", type=str, default="2")
    p.add_argument("--leverage", type=int, default=3)
    p.add_argument("--max-loss-pct", type=str, default="0.08")
    p.add_argument("--wallet-usdt", type=str, default="10",
                   help="known wallet size for loss-limit math")
    p.add_argument("--daily-loss-limit-usdt", type=str, default="1.5",
                   help="positive USDT amount; breach pauses trading until rollover")
    p.add_argument("--consecutive-loss-limit", type=int, default=3)
    p.add_argument("--max-open-positions", type=int, default=2)
    p.add_argument("--per-cycle-trade-cap", type=int, default=5)
    p.add_argument("--cooldown-minutes", type=int, default=60,
                   help="cooldown after consecutive-loss breach")
    p.add_argument("--skip-permission-check", action="store_true",
                   help="(testnet only) skip the withdrawal-permission probe")
    p.add_argument("--reconcile-first", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if not args.i_understand_this_fires_trades_without_asking:
        print(json.dumps({
            "error": "refusing to run without "
                     "--i-understand-this-fires-trades-without-asking",
            "explanation": (
                "FULL_AUTO_LIVE places real Binance Futures orders without "
                "per-trade approval. Default base URL is testnet — set "
                "BINANCE_LIVE=true for mainnet. Either way, this fires "
                "trades for you and you have to acknowledge that."
            ),
        }, indent=2))
        return 2

    cycle_started = dt.datetime.utcnow()
    report: dict[str, Any] = {
        "workflow_status": "running",
        "mode": "FULL_AUTO_LIVE",
        "started_at": cycle_started.isoformat(timespec="seconds") + "Z",
        "warnings": [],
    }

    # --- 1) Public market data + safety health ---
    public_client = BinanceClient()
    market = MarketData(public_client)

    health = run_health_check(public_client)
    report["safety_health"] = health.to_jsonable()
    if not health.trading_allowed:
        report["workflow_status"] = "halted"
        report["next_actions"] = ["resolve safety health warnings"]
        _emit(report)
        return 0

    # --- 2) Safety state: rollover + can-trade gate ---
    limits = SafetyLimits(
        wallet_usdt=Decimal(args.wallet_usdt),
        daily_loss_limit_usdt=Decimal(args.daily_loss_limit_usdt),
        consecutive_loss_limit=args.consecutive_loss_limit,
        max_open_positions=args.max_open_positions,
        no_duplicate_symbol=True,
        per_cycle_trade_cap=args.per_cycle_trade_cap,
        cooldown_minutes_after_consecutive_losses=args.cooldown_minutes,
    )
    safety = SafetyStateManager(limits=limits)
    state, did_rollover = safety.perform_daily_rollover_if_needed()
    if did_rollover:
        report["warnings"].append("daily rollover performed (new UTC day)")

    state, can_trade, reason = safety.check_can_trade(force_rollover_check=False)
    report["safety_state"] = state.to_jsonable()
    report["safety_state"]["can_trade"] = can_trade
    report["safety_state"]["reason"] = reason
    if not can_trade:
        report["workflow_status"] = "halted"
        report["next_actions"] = [
            f"safety state blocks trading: {reason}",
            "use `python -m scripts.run_safety_reset --resume` if you've "
            "verified it's safe to resume manually",
        ]
        _emit(report)
        return 0

    # --- 3) Signed client + permission preflight ---
    signed_client = SignedClient()
    signed_client.enable_signed_requests()
    account = Account(signed_client)
    if not args.skip_permission_check:
        perms = account.check_permissions()
        report["permissions"] = {
            "trading_enabled": perms.trading_enabled,
            "withdrawals_enabled": perms.withdrawals_enabled,
            "is_safe_to_trade": perms.is_safe_to_trade,
            "notes": list(perms.notes),
        }
        if not perms.is_safe_to_trade:
            report["workflow_status"] = "halted"
            _emit(report)
            return 1

    # --- 4) Optional reconcile ---
    if args.reconcile_first:
        try:
            recon = reconcile_via_apis(account=account)
            report["reconciliation"] = recon.to_jsonable()
            if not recon.is_clean:
                # Hard stop — never auto-trade with mismatched state.
                safety.pause(
                    f"position-manager mismatch ({len(recon.mismatches)} entries)",
                    carry_over_rollover=True,
                )
                report["workflow_status"] = "halted"
                _emit(report)
                return 1
        except Exception as e:
            report["warnings"].append(f"reconciliation failed: {e!r}")

    # --- 5) Build router (FULL_AUTO_LIVE) ---
    live_exec = LiveExecution(signed_client)
    router = ExecutionRouter(
        live_execution=live_exec,
        approval_policy=ApprovalPolicy(),     # not consulted in FULL_AUTO_LIVE
        approvals_store=PendingApprovalsStore(),
    )
    # Mark first-trade flag — in FULL_AUTO_LIVE this is the user's express
    # decision; defensive "first trade asks" is for SEMI_AUTO_LIVE only.
    router._first_live_trade_done = True

    # --- 6) Screen + research ---
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

    pos_store = PositionsStore()
    routed_outcomes: list[dict[str, Any]] = []
    opened_positions: list[dict[str, Any]] = []
    fired_this_cycle = 0

    for spec, ticker in candidates_for_research:
        # --- 7) Re-check safety + limits before EVERY proposal ---
        state, can_trade, reason = safety.check_can_trade(force_rollover_check=False)
        if not can_trade:
            report["warnings"].append(f"mid-cycle safety stop: {reason}")
            break

        limit_check = check_proposal(
            state=state, limits=limits, proposed_symbol=spec.symbol,
            open_positions=pos_store.load_open(),
            fired_this_cycle=fired_this_cycle,
        )
        if not limit_check.ok:
            # If a hard cap (paused / daily / consec / per_cycle) is breached
            # we stop the whole cycle. Soft caps (max_open / duplicate) just
            # skip this proposal.
            hard = {"paused", "daily_loss_limit", "consecutive_loss_limit",
                    "per_cycle_trade_cap"}
            if any(b in hard for b in limit_check.breached):
                report["warnings"].append(
                    f"limits cap reached: {', '.join(limit_check.reasons)}"
                )
                break
            # Skip this proposal, try the next.
            append_rejection({
                "rejection_id": make_rejection_id(seq=len(routed_outcomes) + 1),
                "proposal_id": make_proposal_id(spec.symbol, seq=len(routed_outcomes) + 1),
                "mode": "FULL_AUTO_LIVE", "symbol": spec.symbol,
                "side": "?", "strategy": "(pre-strategy)",
                "proposed_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "rejected_by": "limits",
                "rejection_reason": "; ".join(limit_check.reasons),
                "market_regime": "unknown",
                "hindsight_outcome": "unclear", "hindsight_notes": "",
            })
            routed_outcomes.append({
                "symbol": spec.symbol,
                "status": "limits_skipped",
                "reasons": list(limit_check.reasons),
            })
            continue

        # --- 8) Research → strategy → risk ---
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

        entry = round_price(spec, (best.entry_zone[0] + best.entry_zone[1]) / Decimal("2"),
                            mode="down")
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
                "mode": "FULL_AUTO_LIVE", "symbol": spec.symbol,
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
        try:
            live_exec.set_leverage(spec.symbol, sizing.leverage)
        except Exception as e:
            report["warnings"].append(f"set_leverage {spec.symbol} failed: {e!r}")

        # --- 9) Route through router with FULL_AUTO_LIVE ---
        outcome = router.route(
            mode="FULL_AUTO_LIVE", proposal_id=proposal_id,
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
                market_regime="full_auto_live",
                opened_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                updated_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                closed_at=None, exit_price=None, exit_reason=None,
                mode="FULL_AUTO_LIVE",
                order_ids=[str(outcome.order_id)] if outcome.order_id else [],
                notes=["fired by FULL_AUTO_LIVE cycle"],
            )
            pos_store.upsert(position)
            opened_positions.append({
                "position_id": position.position_id,
                "symbol": spec.symbol, "side": best.side,
                "strategy": best.strategy,
                "entry_price": str(position.entry_price),
                "quantity": str(position.quantity),
                "stop_loss": str(stop),
                "take_profit_targets": [str(t) for t in position.take_profit_targets],
                "order_id": outcome.order_id,
            })
            fired_this_cycle += 1

    report["routed_outcomes"] = routed_outcomes
    report["opened_positions"] = opened_positions

    # Final safety snapshot.
    final_state = safety.load()
    report["safety_state_after"] = final_state.to_jsonable()

    filled = [r for r in routed_outcomes if r.get("status") == "filled"]
    rejected = [r for r in routed_outcomes if r.get("status") in ("risk_rejected", "rejected")]
    skipped = [r for r in routed_outcomes if r.get("status") == "limits_skipped"]
    report["summary"] = {
        "tokens_researched": len([s for s, _ in candidates_for_research]),
        "auto_filled": len(filled),
        "rejected": len(rejected),
        "skipped_by_limits": len(skipped),
    }
    next_actions: list[str] = []
    if filled:
        next_actions.append(
            "Run `python -m scripts.run_watch_positions --loop` to manage open positions."
        )
    if final_state.trading_paused:
        next_actions.append(
            f"safety paused: {final_state.paused_reason}. "
            "Use `python -m scripts.run_safety_reset --resume` to clear."
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
