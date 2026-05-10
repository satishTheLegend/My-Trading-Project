"""End-to-end paper-trading cycle.

Wires together every Phase 2 module into the workflow defined in
agency/workflow.md, but executes in PAPER_TRADING mode only — no order
placement, no signed requests.

Usage::

    python -m scripts.run_paper_cycle [--top N] [--save] [--symbol DOGEUSDT]

Outputs:
  - structured JSON cycle report to stdout
  - if ``--save`` is passed, persists cycle state to data/agency-state.json
    and appends a journal entry for any trade proposal that gets approved
    (still paper — no real order)

This is the proof-of-life for Phase 2. Phase 3 wraps a tighter loop with
exit simulation; Phase 4 swaps the simulated execution step for live
testnet orders.
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

from .binance_client import BinanceClient
from .health_check import run_health_check
from .journal_writer import (
    append_rejection, make_proposal_id, make_rejection_id,
)
from .market_data import MarketData
from .paper_execution import simulate_market_fill
from .positions_store import Position, PositionsStore, make_position_id
from .risk_engine import RiskConfig, evaluate_proposal
from .strategy_scoring import rank_strategies
from .symbol_filters import parse_exchange_info, round_price
from .token_research import research_token
from .token_screener import ScreeningConfig, run_screener


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENCY_STATE = _PROJECT_ROOT / "data" / "agency-state.json"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run one paper-trading cycle")
    p.add_argument("--top", type=int, default=3, help="research the top N screened candidates")
    p.add_argument("--save", action="store_true", help="persist cycle outputs to data/ + memory/")
    p.add_argument("--symbol", help="bypass screener and research a single symbol")
    p.add_argument("--min-quote-volume", type=str, default="5000000",
                   help="minimum 24h quote volume USDT (default 5M)")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    client = BinanceClient()
    market = MarketData(client)
    cycle_started = dt.datetime.utcnow()

    report: dict[str, Any] = {
        "workflow_status": "running",
        "mode": "PAPER_TRADING",
        "started_at": cycle_started.isoformat(timespec="seconds") + "Z",
        "warnings": [],
    }

    # ----- Step 1: Safety / health check ---------------------------------
    health = run_health_check(client)
    report["safety"] = health.to_jsonable()
    if not health.trading_allowed:
        report["workflow_status"] = "halted"
        report["next_actions"] = ["resolve safety warnings before running again"]
        _emit(report, args.save)
        return 0

    # ----- Step 2: market context (lightweight) --------------------------
    # Quick BTC sanity check — if BTC just moved violently, treat as warning.
    try:
        btc_klines = market.get_klines("BTCUSDT", "1h", limit=12)
        if btc_klines:
            last = btc_klines[-1]
            change_pct = float((last.close - last.open) / last.open * Decimal("100"))
            report["market_context"] = {
                "btc_last_1h_change_pct": round(change_pct, 3),
                "btc_close": str(last.close),
            }
            if abs(change_pct) >= 2.0:
                report["warnings"].append(
                    f"BTC moved {change_pct:.2f}% in the last 1h — small caps will be jumpy"
                )
    except Exception as e:
        report["warnings"].append(f"BTC market context unavailable: {e!r}")

    # ----- Step 3: token screening ---------------------------------------
    if args.symbol:
        report["screener"] = {"skipped": True, "reason": f"--symbol={args.symbol}"}
        # Build a minimal candidate list of 1.
        info = market.get_exchange_info()
        specs = parse_exchange_info(info)
        if args.symbol not in specs:
            report["workflow_status"] = "halted"
            report["warnings"].append(f"unknown symbol {args.symbol}")
            _emit(report, args.save)
            return 1
        spec = specs[args.symbol]
        ticker = market.get_ticker_24h(args.symbol)
        candidates_for_research = [(spec, ticker)]
    else:
        cfg = ScreeningConfig(
            min_24h_quote_volume_usdt=Decimal(args.min_quote_volume),
            max_candidates=max(args.top, 5),
        )
        screening = run_screener(market, cfg)
        report["screener"] = screening.to_jsonable()

        if not screening.candidates:
            report["workflow_status"] = "no_candidates"
            report["next_actions"] = ["loosen screening filters or check market regime"]
            _emit(report, args.save)
            return 0

        # Resolve specs/tickers for the top N
        info = market.get_exchange_info()
        specs = parse_exchange_info(info)
        # We need the Ticker24h for each top candidate. The screener already
        # had them — re-fetch to keep typing simple (cost: 1 weight per symbol
        # × ≤5 = trivial).
        candidates_for_research = []
        for c in screening.candidates[: args.top]:
            spec = specs.get(c.symbol)
            if spec is None:
                continue
            ticker = market.get_ticker_24h(c.symbol)
            candidates_for_research.append((spec, ticker))

    # ----- Step 4: deep research + 5: strategy + 6: trade decision -------
    research_results: list[dict[str, Any]] = []
    rankings: list[dict[str, Any]] = []
    risk_evaluations: list[dict[str, Any]] = []

    for spec, ticker in candidates_for_research:
        try:
            research = research_token(market, spec, ticker_24h=ticker)
        except Exception as e:
            report["warnings"].append(f"research failed for {spec.symbol}: {e!r}")
            continue
        research_results.append(research.to_jsonable())

        ranking = rank_strategies(research)
        rankings.append(ranking.to_jsonable())

        if ranking.best is None:
            # Log a rejection for the top scored strategy regardless.
            top = ranking.scores[0] if ranking.scores else None
            if args.save and top:
                append_rejection({
                    "rejection_id": make_rejection_id(seq=len(risk_evaluations) + 1),
                    "proposal_id": make_proposal_id(spec.symbol, seq=len(risk_evaluations) + 1),
                    "mode": "PAPER_TRADING",
                    "symbol": spec.symbol,
                    "side": top.side,
                    "strategy": top.strategy,
                    "proposed_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "rejected_by": "trade-decision",
                    "rejection_reason": "no strategy met MIN_CONFIDENCE",
                    "market_regime": "unknown",
                    "hindsight_outcome": "unclear",
                    "hindsight_notes": "",
                })
            continue

        # ----- 7: risk approval ------------------------------------------
        best = ranking.best
        if not best.entry_zone or best.invalidation is None or not best.take_profit_targets:
            report["warnings"].append(
                f"{spec.symbol} top strategy {best.strategy} missing entry/stop/TP — skipping"
            )
            continue

        entry_mid = (best.entry_zone[0] + best.entry_zone[1]) / Decimal("2")
        # Round to symbol tick size so the price is exchange-valid.
        entry = round_price(spec, entry_mid, mode="down")
        stop = round_price(spec, best.invalidation, mode="down" if best.side == "LONG" else "up")
        tp1 = round_price(spec, best.take_profit_targets[0], mode="down" if best.side == "LONG" else "up")

        proposal_id = make_proposal_id(spec.symbol, seq=len(risk_evaluations) + 1)
        approval = evaluate_proposal(
            proposal_id=proposal_id,
            spec=spec,
            side=best.side,
            entry_price=entry,
            stop_price=stop,
            take_profit_price=tp1,
            cfg=RiskConfig(),
        )
        risk_evaluations.append({
            "symbol": spec.symbol,
            "strategy": best.strategy,
            "side": best.side,
            "entry": str(entry),
            "stop": str(stop),
            "tp1": str(tp1),
            "approval": approval.to_jsonable(),
        })

        if args.save:
            if approval.risk_decision == "approved" and approval.sizing is not None:
                # Phase 3 wiring: simulate the entry fill against the live order
                # book, persist the open position to data/open-positions.json so
                # the watcher can manage it. The trade-journal entry is written
                # later by the watcher when the position closes.
                book = market.get_order_book(spec.symbol, limit=20)
                fill = simulate_market_fill(best.side, approval.sizing.quantity, book)
                if not fill.is_complete:
                    report["warnings"].append(
                        f"{spec.symbol}: simulated fill incomplete — book too thin "
                        f"({fill.notes}). Skipping."
                    )
                    append_rejection({
                        "rejection_id": make_rejection_id(seq=len(risk_evaluations)),
                        "proposal_id": proposal_id,
                        "mode": "PAPER_TRADING",
                        "symbol": spec.symbol,
                        "side": best.side,
                        "strategy": best.strategy,
                        "proposed_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                        "rejected_by": "execution-agent",
                        "rejection_reason": f"thin order book: {fill.notes}",
                        "market_regime": "unknown",
                        "hindsight_outcome": "unclear",
                        "hindsight_notes": "",
                    })
                    continue

                position = Position(
                    position_id=make_position_id(spec.symbol, seq=len(risk_evaluations)),
                    symbol=spec.symbol,
                    side=best.side,
                    status="open",
                    entry_price=fill.average_price,
                    quantity=fill.filled_qty,
                    initial_quantity=fill.filled_qty,
                    leverage=approval.sizing.leverage,
                    margin_mode="ISOLATED",
                    margin_usdt=approval.sizing.margin_usdt,
                    notional_usdt=fill.notional_usdt,
                    stop_loss=stop,
                    take_profit_targets=[
                        round_price(spec, t, mode="down" if best.side == "LONG" else "up")
                        for t in best.take_profit_targets
                    ],
                    unrealized_pnl=Decimal("0"),
                    realized_pnl=-fill.fees_usdt,    # entry fee already a loss
                    max_favorable_pnl=Decimal("0"),
                    max_adverse_pnl=Decimal("0"),
                    liquidation_price=approval.liquidation.liquidation_price if approval.liquidation else None,
                    fees_paid_usdt=fill.fees_usdt,
                    funding_paid_usdt=Decimal("0"),
                    proposal_id=proposal_id,
                    strategy=best.strategy,
                    market_regime=report.get("market_context", {}).get("regime", "unknown"),
                    opened_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    updated_at=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    closed_at=None,
                    exit_price=None,
                    exit_reason=None,
                    mode="PAPER_TRADING",
                    notes=[
                        f"opened via paper_execution; fill slippage {fill.slippage_bps:.2f} bps",
                    ],
                )
                store = PositionsStore()
                store.upsert(position)

                report.setdefault("opened_positions", []).append({
                    "position_id": position.position_id,
                    "symbol": spec.symbol,
                    "side": best.side,
                    "strategy": best.strategy,
                    "entry_price": str(fill.average_price),
                    "quantity": str(fill.filled_qty),
                    "stop_loss": str(stop),
                    "take_profit_targets": [str(t) for t in position.take_profit_targets],
                    "fill_slippage_bps": str(fill.slippage_bps),
                })
            else:
                append_rejection({
                    "rejection_id": make_rejection_id(seq=len(risk_evaluations)),
                    "proposal_id": proposal_id,
                    "mode": "PAPER_TRADING",
                    "symbol": spec.symbol,
                    "side": best.side,
                    "strategy": best.strategy,
                    "proposed_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "rejected_by": "risk-manager",
                    "rejection_reason": approval.risk_reason,
                    "market_regime": "unknown",
                    "hindsight_outcome": "unclear",
                    "hindsight_notes": "",
                })

    report["research"] = research_results
    report["strategy_rankings"] = rankings
    report["risk_evaluations"] = risk_evaluations

    # ----- 17: user-facing summary ---------------------------------------
    approved = [r for r in risk_evaluations if r["approval"]["risk_decision"] == "approved"]
    report["summary"] = {
        "candidates_screened": len(report.get("screener", {}).get("candidates", [])) if "candidates" in report.get("screener", {}) else 1,
        "tokens_researched": len(research_results),
        "strategies_with_signal": sum(1 for rk in rankings if rk["best_strategy"] is not None),
        "approved_proposals": len(approved),
        "approved_symbols": [a["symbol"] for a in approved],
        "opened_positions_count": len(report.get("opened_positions", [])),
    }
    if report.get("opened_positions"):
        report["next_actions"] = [
            "Run `python -m scripts.run_watch_positions` (or `--loop`) to manage open paper positions.",
        ]

    report["workflow_status"] = "complete"
    report["finished_at"] = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    _emit(report, args.save)
    return 0


def _emit(report: dict[str, Any], save: bool) -> None:
    sys.stdout.write(json.dumps(report, indent=2, default=str))
    sys.stdout.write("\n")
    sys.stdout.flush()
    if save:
        AGENCY_STATE.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if AGENCY_STATE.exists():
            try:
                existing = json.loads(AGENCY_STATE.read_text())
            except ValueError:
                pass
        existing.update({
            "mode": "PAPER_TRADING",
            "last_cycle_at": report.get("finished_at") or report.get("started_at"),
            "last_cycle_status": report.get("workflow_status"),
            "live_mode_explicitly_enabled": False,
            "last_summary": report.get("summary"),
        })
        AGENCY_STATE.write_text(json.dumps(existing, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
