"""Persistent paper-position store.

Backs ``data/open-positions.json``. The Position Manager Agent reads/writes
through this module — never directly. Atomic writes use a temp-file + rename
so a crash mid-write never corrupts the canonical file.

The on-disk schema follows CLAUDE.md's Standard Position State Format. Internal
``Position`` dataclass uses Decimal for all prices/quantities (no float drift).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPEN_POSITIONS = _PROJECT_ROOT / "data" / "open-positions.json"

# Position lifecycle states from CLAUDE.md's Standard Position State Format.
VALID_STATUSES = (
    "proposed", "approved", "order_pending", "open",
    "partial_exit", "closing", "closed", "error",
)


@dataclass
class Position:
    position_id: str
    symbol: str
    side: str                            # "LONG" | "SHORT"
    status: str                          # see VALID_STATUSES
    entry_price: Decimal
    quantity: Decimal                    # remaining open qty (decreases on partial exits)
    initial_quantity: Decimal            # original fill qty
    leverage: int
    margin_mode: str                     # "ISOLATED" | "CROSS"
    margin_usdt: Decimal
    notional_usdt: Decimal
    stop_loss: Decimal | None
    take_profit_targets: list[Decimal]
    unrealized_pnl: Decimal              # quote-asset, snapshot at last update
    realized_pnl: Decimal                # cumulative across partial exits
    max_favorable_pnl: Decimal           # best mark-to-market PnL seen
    max_adverse_pnl: Decimal             # worst mark-to-market PnL seen
    liquidation_price: Decimal | None
    fees_paid_usdt: Decimal              # cumulative
    funding_paid_usdt: Decimal           # cumulative (paper mode rarely populates)
    proposal_id: str
    strategy: str
    market_regime: str
    opened_at: str                       # ISO timestamp
    updated_at: str
    closed_at: str | None
    exit_price: Decimal | None
    exit_reason: str | None
    mode: str = "PAPER_TRADING"
    order_ids: list[str] = field(default_factory=list)
    mistake_tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ helpers

    @property
    def is_open(self) -> bool:
        return self.status in ("open", "partial_exit", "order_pending", "closing")

    def mark_to_market(self, mark_price: Decimal) -> Decimal:
        """Return the mark-to-market unrealized PnL at ``mark_price``.

        Does NOT mutate. The watcher calls this every tick and then either
        records the new MFE/MAE via ``update_pnl`` or triggers an exit.
        """
        if self.side == "LONG":
            per_unit = mark_price - self.entry_price
        else:
            per_unit = self.entry_price - mark_price
        return per_unit * self.quantity

    def update_pnl(self, mark_price: Decimal) -> None:
        unrealized = self.mark_to_market(mark_price)
        self.unrealized_pnl = unrealized
        if unrealized > self.max_favorable_pnl:
            self.max_favorable_pnl = unrealized
        if unrealized < self.max_adverse_pnl:
            self.max_adverse_pnl = unrealized
        self.updated_at = _now_iso()

    # ------------------------------------------------------------------ serdes

    def to_jsonable(self) -> dict[str, Any]:
        d = asdict(self)
        for k, v in list(d.items()):
            if isinstance(v, Decimal):
                d[k] = str(v)
            elif isinstance(v, list) and v and isinstance(v[0], Decimal):
                d[k] = [str(x) for x in v]
        return d

    @classmethod
    def from_jsonable(cls, d: dict[str, Any]) -> "Position":
        kw: dict[str, Any] = {}
        decimal_fields = {
            "entry_price", "quantity", "initial_quantity", "margin_usdt",
            "notional_usdt", "unrealized_pnl", "realized_pnl",
            "max_favorable_pnl", "max_adverse_pnl", "fees_paid_usdt",
            "funding_paid_usdt",
        }
        nullable_decimal_fields = {"stop_loss", "liquidation_price", "exit_price"}
        list_decimal_fields = {"take_profit_targets"}

        for k, v in d.items():
            if k in decimal_fields:
                kw[k] = Decimal(str(v))
            elif k in nullable_decimal_fields:
                kw[k] = Decimal(str(v)) if v not in (None, "", "null") else None
            elif k in list_decimal_fields:
                kw[k] = [Decimal(str(x)) for x in (v or [])]
            elif k == "leverage":
                kw[k] = int(v)
            else:
                kw[k] = v
        # Provide defaults for any optional fields missing in older JSON.
        kw.setdefault("mode", "PAPER_TRADING")
        kw.setdefault("order_ids", [])
        kw.setdefault("mistake_tags", [])
        kw.setdefault("notes", [])
        return cls(**kw)


# ----------------------------------------------------------------------------
# Store
# ----------------------------------------------------------------------------


class PositionsStore:
    """Thin layer over data/open-positions.json with atomic writes.

    Schema::

        {
          "positions": [ Position.to_jsonable(), ... ],
          "last_reconciled_at": "..."
        }
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or OPEN_POSITIONS

    # ----- read --------------------------------------------------------

    def load_all(self) -> list[Position]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        out: list[Position] = []
        for raw in data.get("positions", []):
            try:
                out.append(Position.from_jsonable(raw))
            except Exception:
                # Skip malformed entries — never crash the watcher on one bad row.
                continue
        return out

    def load_open(self) -> list[Position]:
        return [p for p in self.load_all() if p.is_open]

    def find(self, position_id: str) -> Position | None:
        for p in self.load_all():
            if p.position_id == position_id:
                return p
        return None

    def find_by_symbol(self, symbol: str) -> list[Position]:
        return [p for p in self.load_all() if p.symbol == symbol]

    # ----- write -------------------------------------------------------

    def save_all(self, positions: Iterable[Position]) -> None:
        data = {
            "positions": [p.to_jsonable() for p in positions],
            "last_reconciled_at": _now_iso(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(json.dumps(data, indent=2))

    def upsert(self, position: Position) -> None:
        all_pos = self.load_all()
        idx = next((i for i, p in enumerate(all_pos) if p.position_id == position.position_id), None)
        if idx is None:
            all_pos.append(position)
        else:
            all_pos[idx] = position
        self.save_all(all_pos)

    def remove_closed(self, *, keep_last_n: int | None = None) -> int:
        """Drop closed positions from the file.

        Optionally keep the last ``keep_last_n`` closed positions for context;
        the rest are pruned (already journaled, so no information loss).

        Returns the number removed.
        """
        all_pos = self.load_all()
        open_p = [p for p in all_pos if p.is_open]
        closed_p = [p for p in all_pos if not p.is_open]
        if keep_last_n is not None and keep_last_n > 0:
            closed_p.sort(key=lambda p: p.closed_at or "", reverse=True)
            keep = closed_p[:keep_last_n]
        else:
            keep = []
        new_all = open_p + keep
        removed = len(all_pos) - len(new_all)
        self.save_all(new_all)
        return removed

    # ----- internals ---------------------------------------------------

    def _atomic_write(self, content: str) -> None:
        # Write to a sibling temp file then rename — atomic on POSIX.
        d = self.path.parent
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=d, prefix=".tmp.", delete=False
        ) as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self.path)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def make_position_id(symbol: str, when: dt.datetime | None = None, seq: int = 1) -> str:
    when = when or dt.datetime.utcnow()
    return f"POS-{when:%Y%m%d-%H%M%S}-{symbol}-{seq:03d}"


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


__all__ = [
    "Position",
    "PositionsStore",
    "OPEN_POSITIONS",
    "VALID_STATUSES",
    "make_position_id",
]
