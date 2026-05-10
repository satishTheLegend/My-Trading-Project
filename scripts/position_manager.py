"""Position Manager — reconcile internal state with Binance.

Compares the local `data/open-positions.json` against `/fapi/v2/positionRisk`
and produces a `ReconciliationReport`. Mismatch categories:

  - missing_on_exchange   — local says open, Binance says flat or different side
  - missing_locally       — Binance has a position we don't track
  - qty_mismatch          — same side but different absolute qty
  - side_mismatch         — local LONG, exchange SHORT (or vice versa)
  - status_drift          — local "closing" but exchange still shows non-zero qty

By default a single mismatch is treated as a Safety Agent emergency: the
Position Manager's job is to never let internal state drift unobserved.
The orchestrator may call `record_health(report, store)` to update
`data/system-health.json` and pause the agency on mismatch.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from .account import Account, ExchangePosition
from .positions_store import Position, PositionsStore

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_HEALTH = _PROJECT_ROOT / "data" / "system-health.json"

# Tolerance for qty comparison. Binance reports qty to symbol precision;
# our local store uses Decimal strings that should match exactly. We allow a
# tiny epsilon for floating-point round-trips through serialization.
QTY_TOLERANCE = Decimal("0.000000001")


# ----------------------------------------------------------------------------
# Types
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Mismatch:
    kind: str                       # see categories above
    symbol: str
    local: dict[str, Any] | None
    exchange: dict[str, Any] | None
    detail: str

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "symbol": self.symbol,
            "local": self.local,
            "exchange": self.exchange,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ReconciliationReport:
    timestamp: str
    local_open_count: int
    exchange_open_count: int
    matched: int
    mismatches: tuple[Mismatch, ...]

    @property
    def is_clean(self) -> bool:
        return not self.mismatches

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "local_open_count": self.local_open_count,
            "exchange_open_count": self.exchange_open_count,
            "matched": self.matched,
            "is_clean": self.is_clean,
            "mismatches": [m.to_jsonable() for m in self.mismatches],
        }


# ----------------------------------------------------------------------------
# Reconciler
# ----------------------------------------------------------------------------


def reconcile(
    *,
    local_positions: list[Position],
    exchange_positions: list[ExchangePosition],
    qty_tolerance: Decimal = QTY_TOLERANCE,
) -> ReconciliationReport:
    """Pure reconciler — no I/O. Easy to unit-test with synthetic inputs.

    Two-pass:
      pass 1: walk locals, find each in the exchange map. categorize.
      pass 2: walk exchange positions left over → ``missing_locally``.
    """
    local_open = [p for p in local_positions if p.is_open]
    exch_by_symbol: dict[str, ExchangePosition] = {p.symbol: p for p in exchange_positions if p.is_open}

    mismatches: list[Mismatch] = []
    matched = 0
    seen_exch_symbols: set[str] = set()

    for lp in local_open:
        ep = exch_by_symbol.get(lp.symbol)
        if ep is None:
            mismatches.append(Mismatch(
                kind="missing_on_exchange",
                symbol=lp.symbol,
                local=_local_summary(lp),
                exchange=None,
                detail="local says open, exchange has no position",
            ))
            continue
        seen_exch_symbols.add(lp.symbol)
        if lp.side != ep.side:
            mismatches.append(Mismatch(
                kind="side_mismatch",
                symbol=lp.symbol,
                local=_local_summary(lp),
                exchange=_exch_summary(ep),
                detail=f"local {lp.side} vs exchange {ep.side}",
            ))
            continue
        if abs(lp.quantity - ep.quantity) > qty_tolerance:
            mismatches.append(Mismatch(
                kind="qty_mismatch",
                symbol=lp.symbol,
                local=_local_summary(lp),
                exchange=_exch_summary(ep),
                detail=f"local qty {lp.quantity} vs exchange qty {ep.quantity}",
            ))
            continue
        if lp.status == "closing":
            mismatches.append(Mismatch(
                kind="status_drift",
                symbol=lp.symbol,
                local=_local_summary(lp),
                exchange=_exch_summary(ep),
                detail="local marked 'closing' but exchange still has non-zero qty",
            ))
            continue
        matched += 1

    leftover = [ep for sym, ep in exch_by_symbol.items() if sym not in seen_exch_symbols]
    for ep in leftover:
        # An exchange position not tracked locally is *always* dangerous —
        # something opened it (manual? leftover from a crashed cycle?).
        mismatches.append(Mismatch(
            kind="missing_locally",
            symbol=ep.symbol,
            local=None,
            exchange=_exch_summary(ep),
            detail="exchange has position with no local record",
        ))

    return ReconciliationReport(
        timestamp=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        local_open_count=len(local_open),
        exchange_open_count=len(exch_by_symbol),
        matched=matched,
        mismatches=tuple(mismatches),
    )


# ----------------------------------------------------------------------------
# Convenience
# ----------------------------------------------------------------------------


def reconcile_via_apis(
    account: Account | None = None,
    store: PositionsStore | None = None,
) -> ReconciliationReport:
    """Fetch both sides and reconcile. Used by the CLI + watcher."""
    account = account or Account()
    store = store or PositionsStore()
    local = store.load_open()
    exch = account.get_open_positions()
    return reconcile(local_positions=local, exchange_positions=exch)


def record_health(report: ReconciliationReport, *, pause_on_mismatch: bool = True) -> None:
    """Update data/system-health.json with the reconciliation outcome.

    On mismatch + ``pause_on_mismatch=True`` the agency pauses (matches the
    behavior the Safety Agent expects from `agency/safety-rules.md`).
    """
    SYSTEM_HEALTH.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if SYSTEM_HEALTH.exists():
        try:
            existing = json.loads(SYSTEM_HEALTH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
    existing.update({
        "last_reconciliation_at": report.timestamp,
        "last_reconciliation_clean": report.is_clean,
        "last_reconciliation_mismatch_count": len(report.mismatches),
    })
    if not report.is_clean and pause_on_mismatch:
        existing["trading_paused"] = True
        existing["paused_reason"] = (
            f"position-manager detected {len(report.mismatches)} mismatch(es); "
            "see /monitor-open-positions output for details"
        )
    SYSTEM_HEALTH.write_text(json.dumps(existing, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------------


def _local_summary(p: Position) -> dict[str, Any]:
    return {
        "position_id": p.position_id,
        "side": p.side,
        "quantity": str(p.quantity),
        "entry_price": str(p.entry_price),
        "status": p.status,
        "opened_at": p.opened_at,
    }


def _exch_summary(p: ExchangePosition) -> dict[str, Any]:
    return {
        "side": p.side,
        "quantity": str(p.quantity),
        "entry_price": str(p.entry_price),
        "mark_price": str(p.mark_price),
        "leverage": p.leverage,
        "margin_type": p.margin_type,
        "liquidation_price": str(p.liquidation_price) if p.liquidation_price is not None else None,
    }


__all__ = [
    "Mismatch",
    "ReconciliationReport",
    "QTY_TOLERANCE",
    "reconcile",
    "reconcile_via_apis",
    "record_health",
]
