"""Journal writer — append-only entries to memory/trade-journal.md and
memory/rejected-trades.md.

The Journal & Accounting Agent owns those files. This module just provides
the safe append primitives so multiple cycles can write without clobbering.

Design choices:
  - Appending to markdown (not JSON) because the user reviews these files
    by eye and the schema is intentionally human-readable.
  - One entry = one ``## TRADE-...`` or ``## REJECTED-...`` block, separated
    by a blank line above and below.
  - ``proposal_id`` is required and unique-per-day; we never reformat or
    rewrite past entries.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADE_JOURNAL = _PROJECT_ROOT / "memory" / "trade-journal.md"
REJECTED_TRADES = _PROJECT_ROOT / "memory" / "rejected-trades.md"
SAFETY_EVENTS = _PROJECT_ROOT / "memory" / "safety-events.md"
EXEC_ERRORS = _PROJECT_ROOT / "memory" / "execution-errors.md"


def make_proposal_id(symbol: str, when: dt.datetime | None = None, seq: int = 1) -> str:
    """e.g. PROP-20260510-DOGEUSDT-001"""
    when = when or dt.datetime.utcnow()
    return f"PROP-{when:%Y%m%d}-{symbol}-{seq:03d}"


def make_trade_id(when: dt.datetime | None = None, seq: int = 1) -> str:
    when = when or dt.datetime.utcnow()
    return f"TRADE-{when:%Y%m%d}-{seq:03d}"


def make_rejection_id(when: dt.datetime | None = None, seq: int = 1) -> str:
    when = when or dt.datetime.utcnow()
    return f"REJECTED-{when:%Y%m%d}-{seq:03d}"


def _append_block(path: Path, block: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_default_header(path.name) + "\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        if not block.startswith("\n"):
            f.write("\n")
        f.write(block.rstrip() + "\n")


def _default_header(name: str) -> str:
    return f"# {name}\n\n_Auto-managed by scripts/journal_writer.py — append-only._"


def _kv_line(key: str, value: Any) -> str:
    if isinstance(value, Decimal):
        value = format(value, "f")
    if isinstance(value, (list, tuple)):
        if not value:
            return f"- {key}: []"
        return f"- {key}: [" + ", ".join(_format_scalar(v) for v in value) + "]"
    return f"- {key}: {_format_scalar(value)}"


def _format_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Decimal):
        return format(v, "f")
    return str(v)


# ----------------------------------------------------------------------------
# Public writers
# ----------------------------------------------------------------------------


def append_paper_trade(entry: dict[str, Any]) -> None:
    """Write a paper-trade entry to memory/trade-journal.md.

    ``entry`` should follow the schema in memory/trade-journal.md. Required
    keys:
      proposal_id, mode, symbol, side, strategy, market_regime,
      entry_time, entry_price, quantity, leverage, margin_mode, margin_usdt,
      notional_usdt, stop_loss, take_profit_targets, exit_time, exit_price,
      exit_reason, gross_pnl_usdt, fees_usdt, funding_usdt, slippage_usdt,
      net_pnl_usdt, max_favorable_pnl_usdt, max_adverse_pnl_usdt,
      mistake_tags, lessons, order_ids
    """
    trade_id = entry.get("trade_id") or make_trade_id()
    lines = [f"\n## {trade_id}\n"]
    for k in (
        "proposal_id", "mode", "symbol", "side", "strategy", "market_regime",
        "entry_time", "entry_price", "quantity", "leverage", "margin_mode",
        "margin_usdt", "notional_usdt", "stop_loss", "take_profit_targets",
        "exit_time", "exit_price", "exit_reason", "gross_pnl_usdt",
        "fees_usdt", "funding_usdt", "slippage_usdt", "net_pnl_usdt",
        "max_favorable_pnl_usdt", "max_adverse_pnl_usdt", "mistake_tags",
        "lessons", "order_ids",
    ):
        if k in entry:
            lines.append(_kv_line(k, entry[k]))
    _append_block(TRADE_JOURNAL, "\n".join(lines))


def append_rejection(entry: dict[str, Any]) -> None:
    """Write a rejection entry to memory/rejected-trades.md."""
    rid = entry.get("rejection_id") or make_rejection_id()
    lines = [f"\n## {rid}\n"]
    for k in (
        "proposal_id", "mode", "symbol", "side", "strategy", "proposed_at",
        "rejected_by", "rejection_reason", "market_regime",
        "hindsight_outcome", "hindsight_notes",
    ):
        if k in entry:
            lines.append(_kv_line(k, entry[k]))
    _append_block(REJECTED_TRADES, "\n".join(lines))


def append_safety_event(entry: dict[str, Any]) -> None:
    eid = entry.get("event_id") or f"SAFETY-{dt.datetime.utcnow():%Y%m%d-%H%M%S}"
    lines = [f"\n## {eid}\n"]
    for k in (
        "timestamp", "mode", "event_type", "triggered_by", "details",
        "positions_affected", "action_taken", "duration_minutes",
        "resolved_at", "resolution_notes",
    ):
        if k in entry:
            lines.append(_kv_line(k, entry[k]))
    _append_block(SAFETY_EVENTS, "\n".join(lines))


def append_execution_error(entry: dict[str, Any]) -> None:
    eid = entry.get("error_id") or f"ERROR-{dt.datetime.utcnow():%Y%m%d-%H%M%S}"
    lines = [f"\n## {eid}\n"]
    for k in (
        "timestamp", "mode", "symbol", "attempted_action",
        "binance_code", "binance_message", "internal_state", "exchange_state",
        "impact", "resolution", "escalated_to",
    ):
        if k in entry:
            lines.append(_kv_line(k, entry[k]))
    _append_block(EXEC_ERRORS, "\n".join(lines))


__all__ = [
    "TRADE_JOURNAL", "REJECTED_TRADES", "SAFETY_EVENTS", "EXEC_ERRORS",
    "make_proposal_id", "make_trade_id", "make_rejection_id",
    "append_paper_trade", "append_rejection",
    "append_safety_event", "append_execution_error",
]
