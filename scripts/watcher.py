"""Watcher Agent — single monitoring tick over all open paper positions.

For each open `Position`:
  1. Fetch the latest 1m candle + recent ATR window for the symbol.
  2. Update mark-to-market PnL, MFE, MAE.
  3. Run `exit_simulator.decide_from_candle`.
  4. Apply the decision, persist position changes.
  5. If terminal, append a closed-trade entry to memory/trade-journal.md.
  6. Optionally surface an emergency to Safety Agent (caller decides).

Designed for a single tick — looping cadence is the orchestrator's concern.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .exit_simulator import (
    AppliedExit,
    ExitConfig,
    ExitDecision,
    apply_decision,
    decide_from_candle,
)
from .indicators import atr
from .journal_writer import append_paper_trade, append_safety_event
from .market_data import Candle, MarketData
from .positions_store import Position, PositionsStore
from .safety_state import SafetyStateManager


@dataclass
class WatcherTickReport:
    positions_checked: int = 0
    decisions: list[dict[str, Any]] = field(default_factory=list)
    closed: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "positions_checked": self.positions_checked,
            "decisions": self.decisions,
            "closed": self.closed,
            "warnings": self.warnings,
        }


def watch_open_positions(
    market: MarketData,
    *,
    store: PositionsStore | None = None,
    cfg: ExitConfig | None = None,
    candle_interval: str = "1m",
    candle_lookback: int = 30,
    safety_emergency: bool = False,
    safety_manager: SafetyStateManager | None = None,
) -> WatcherTickReport:
    """Run one watcher tick. Returns a structured report.

    The watcher is intentionally idempotent: calling it twice in a row with no
    new candle produces only a HOLD decision with no journal writes. Mark-to-
    market updates *do* persist on every call (so MFE/MAE stays current).

    When a position closes (terminal exit decision), the realized PnL is
    handed to the SafetyStateManager so daily counters + consecutive-loss
    tracking + auto-pause logic stay current. The watcher itself never
    initiates an emergency close — that's an explicit user/safety call —
    but breached limits will pause new entries on the next cycle.
    """
    store = store or PositionsStore()
    cfg = cfg or ExitConfig()
    safety_manager = safety_manager or SafetyStateManager()

    report = WatcherTickReport()
    open_positions = store.load_open()
    report.positions_checked = len(open_positions)
    if not open_positions:
        return report

    all_pos = store.load_all()
    pos_by_id = {p.position_id: p for p in all_pos}

    for pos in open_positions:
        try:
            candles = market.get_klines(pos.symbol, candle_interval, limit=candle_lookback)
        except Exception as e:
            report.warnings.append(f"{pos.symbol}: failed to fetch candles ({e!r})")
            continue
        if not candles:
            report.warnings.append(f"{pos.symbol}: empty candle response")
            continue

        latest = candles[-1]
        # Update mark-to-market on close price (conservative; mark price would
        # be slightly different but we don't always have it for free here).
        pos.update_pnl(latest.close)

        # Compute ATR over the lookback window for trailing logic.
        atr_value: Decimal | None = None
        if len(candles) >= 15:
            atr_series = atr(candles, period=14)
            last_atr = atr_series[-1]
            if last_atr == last_atr:           # not NaN
                atr_value = Decimal(str(last_atr))

        decision = decide_from_candle(
            pos, latest,
            cfg=cfg,
            atr_value=atr_value,
            safety_emergency=safety_emergency,
        )
        applied = apply_decision(pos, decision)

        report.decisions.append({
            "position_id": pos.position_id,
            "symbol": pos.symbol,
            "decision": decision.to_jsonable(),
            "applied": applied.to_jsonable(),
            "unrealized_pnl_after": str(pos.unrealized_pnl),
            "realized_pnl_after": str(pos.realized_pnl),
        })

        # Persist this position back into the master list.
        pos_by_id[pos.position_id] = pos

        if pos.status == "closed":
            report.closed.append({
                "position_id": pos.position_id,
                "symbol": pos.symbol,
                "exit_reason": pos.exit_reason,
                "exit_price": str(pos.exit_price) if pos.exit_price else None,
                "realized_pnl": str(pos.realized_pnl),
            })
            _journal_closed_trade(pos)

            # Update central safety state. ``realized_pnl`` is the position's
            # final net PnL (gross − fees, accumulated across partials). The
            # SafetyStateManager handles auto-pause if a limit is breached.
            try:
                state = safety_manager.record_trade_close(
                    net_pnl_usdt=pos.realized_pnl, symbol=pos.symbol,
                )
                if state.trading_paused and state.paused_reason:
                    report.warnings.append(
                        f"safety pause triggered: {state.paused_reason}"
                    )
            except Exception as e:
                report.warnings.append(f"safety state update failed: {e!r}")

        if applied.decision == "emergency_exit":
            append_safety_event({
                "timestamp": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "mode": pos.mode,
                "event_type": "emergency_exit",
                "triggered_by": "watcher-agent",
                "details": decision.reason,
                "positions_affected": [pos.position_id],
                "action_taken": "closed at market",
                "duration_minutes": 0,
                "resolved_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "resolution_notes": "watcher tick",
            })

    store.save_all(pos_by_id.values())
    return report


# ----------------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------------


def _journal_closed_trade(pos: Position) -> None:
    """Append a fully-realized trade to memory/trade-journal.md."""
    net_pnl = pos.realized_pnl
    entry = {
        "trade_id": f"TRADE-{dt.datetime.utcnow():%Y%m%d-%H%M%S}",
        "proposal_id": pos.proposal_id,
        "mode": pos.mode,
        "symbol": pos.symbol,
        "side": pos.side,
        "strategy": pos.strategy,
        "market_regime": pos.market_regime,
        "entry_time": pos.opened_at,
        "entry_price": str(pos.entry_price),
        "quantity": str(pos.initial_quantity),
        "leverage": pos.leverage,
        "margin_mode": pos.margin_mode,
        "margin_usdt": str(pos.margin_usdt),
        "notional_usdt": str(pos.notional_usdt),
        "stop_loss": str(pos.stop_loss) if pos.stop_loss is not None else "null",
        "take_profit_targets": [str(t) for t in pos.take_profit_targets],
        "exit_time": pos.closed_at,
        "exit_price": str(pos.exit_price) if pos.exit_price is not None else "null",
        "exit_reason": pos.exit_reason or "unknown",
        "gross_pnl_usdt": str(pos.realized_pnl + pos.fees_paid_usdt),
        "fees_usdt": str(pos.fees_paid_usdt),
        "funding_usdt": str(pos.funding_paid_usdt),
        "slippage_usdt": "0",   # already baked into average_price/realized_pnl
        "net_pnl_usdt": str(net_pnl),
        "max_favorable_pnl_usdt": str(pos.max_favorable_pnl),
        "max_adverse_pnl_usdt": str(pos.max_adverse_pnl),
        "mistake_tags": pos.mistake_tags,
        "lessons": "; ".join(pos.notes[-5:]) if pos.notes else "",
        "order_ids": pos.order_ids,
    }
    append_paper_trade(entry)


__all__ = [
    "WatcherTickReport",
    "watch_open_positions",
]
