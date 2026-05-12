"""Persistent paper-position store.

Backs ``data/open-positions.json``. The Position Manager Agent reads/writes
through this module — never directly. Atomic writes use a temp-file + rename
so a crash mid-write never corrupts the canonical file.

The on-disk schema follows CLAUDE.md's Standard Position State Format. Internal
``Position`` dataclass uses Decimal for all prices/quantities (no float drift).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields as dataclass_fields
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

try:                                       # POSIX (Linux, macOS)
    import fcntl
    _HAS_FCNTL = True
except ImportError:                        # Windows fallback
    fcntl = None                           # type: ignore[assignment]
    _HAS_FCNTL = False

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPEN_POSITIONS = _PROJECT_ROOT / "data" / "open-positions.json"

# Whitelist of Position fields the watcher is ALLOWED to mutate via
# ``PositionsStore.apply_watcher_updates``. Everything else (status, stop_loss,
# take_profit_targets, algo_order_ids, quantity, exit_*, closed_at, …) is
# OFF-LIMITS to the watcher — those belong to the execution router, the
# reconciliation paths, or explicit operator scripts. This list is the single
# source of truth and must NOT be widened without an accompanying review of
# the watcher-clobber-race history (see memory/execution-errors.md
# ERROR-20260511-4 and ERROR-20260511-6).
WATCHER_ALLOWED_FIELDS = frozenset({
    "unrealized_pnl",
    "max_favorable_pnl",
    "max_adverse_pnl",
    "updated_at",
    "notes",
})

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
    # Map of logical role → Binance algoId for protective orders on this
    # position, e.g. ``{"sl": 3000001506269526, "tp": 3000001506269544}``.
    # Used by the watcher's trailing-stop logic to cancel-and-replace the SL
    # algo order on the exchange in lock-step with any local stop_loss move.
    # Stored as strings on disk to avoid 64-bit JSON-number precision issues.
    algo_order_ids: dict[str, str] = field(default_factory=dict)

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
        # Forward-compat: silently ignore unknown keys (e.g.
        # ``planned_loss_at_sl_usdt_initial`` is on disk on some live
        # positions but is not yet a Position dataclass field). Without
        # this filter, ``load_all`` raises TypeError on every recent live
        # position, silently drops them via its broad except, and the
        # watcher then sees zero open positions to monitor.
        known = {f.name for f in dataclass_fields(cls)}

        for k, v in d.items():
            if k not in known:
                continue
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
        # Normalize ``algo_order_ids`` — older JSON may not have it; values
        # written by older code (or by humans) may be ints, so coerce to str.
        raw_algo = kw.get("algo_order_ids") or {}
        if isinstance(raw_algo, dict):
            kw["algo_order_ids"] = {str(k): str(v) for k, v in raw_algo.items()}
        else:
            kw["algo_order_ids"] = {}
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
        with self._file_lock():
            self._save_all_locked(list(positions))

    def _save_all_locked(self, positions: Iterable[Position]) -> None:
        data = {
            "positions": [p.to_jsonable() for p in positions],
            "last_reconciled_at": _now_iso(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(json.dumps(data, indent=2))

    def upsert(self, position: Position) -> None:
        with self._file_lock():
            all_pos = self.load_all()
            idx = next((i for i, p in enumerate(all_pos) if p.position_id == position.position_id), None)
            if idx is None:
                all_pos.append(position)
            else:
                all_pos[idx] = position
            self._save_all_locked(all_pos)

    # ----- watcher-scoped upsert --------------------------------------
    # The watcher must NEVER overwrite the whole file. Concurrent writers
    # (execution router, PnL auto-adjust monitor, reconciliation scripts)
    # can land between the watcher's load_all() and its save_all() and the
    # full-file rewrite will clobber their mutations (see
    # memory/execution-errors.md ERROR-20260511-6).
    #
    # ``apply_watcher_updates`` instead:
    #   1. takes an exclusive file lock,
    #   2. re-reads the current file from disk,
    #   3. merges ONLY the whitelisted fields (WATCHER_ALLOWED_FIELDS) into
    #      the positions the watcher actually touched, matched by
    #      position_id and only when the on-disk row is still ``open``,
    #   4. applies monotonic guards on MFE (max ratchets up only) and MAE
    #      (min ratchets down only) so a stale tick can never erase a more
    #      extreme reading written by a concurrent writer,
    #   5. atomically renames the new file into place,
    #   6. releases the lock.
    #
    # Anything outside WATCHER_ALLOWED_FIELDS is silently ignored — the
    # watcher cannot mutate status, stop_loss, take_profit_targets, qty,
    # algo_order_ids, exit_* or closed_at through this entry point.
    def apply_watcher_updates(
        self, updates: dict[str, dict[str, Any]],
    ) -> dict[str, str]:
        """Merge per-position watcher updates without clobbering peers.

        Parameters
        ----------
        updates
            ``{position_id: {field_name: new_value, ...}}``. Field names
            outside ``WATCHER_ALLOWED_FIELDS`` are dropped before merge.
            Values may be Decimal, str, list, or any JSON-serializable type;
            Decimals are coerced to str on write to match the on-disk
            schema. ``notes`` is treated as additive (new entries appended
            to the existing list, deduped against the tail).

        Returns
        -------
        dict[str, str]
            ``{position_id: "merged" | "skipped:<reason>"}`` — for reporting
            and tests. ``skipped:not_open`` if the on-disk row is no longer
            ``open`` (a concurrent close beat us — the right move is to
            stand down). ``skipped:not_found`` if the position_id is gone.
        """
        if not updates:
            return {}

        # Filter to whitelisted fields BEFORE taking the lock so the
        # critical section is as short as possible.
        filtered: dict[str, dict[str, Any]] = {}
        for pid, fields in updates.items():
            clean = {k: v for k, v in fields.items() if k in WATCHER_ALLOWED_FIELDS}
            if clean:
                filtered[pid] = clean
        if not filtered:
            return {}

        outcome: dict[str, str] = {}
        with self._file_lock():
            # Read raw JSON, not deserialised Positions — we need to write
            # back the same shape and the deserialiser may lose
            # forward-compatible fields (e.g. ``planned_loss_at_sl_usdt_initial``
            # which is on disk but not a Position dataclass field).
            if not self.path.exists():
                # Nothing to update against — the watcher must not create
                # the file from scratch.
                return {pid: "skipped:no_file" for pid in filtered}
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {pid: "skipped:read_error" for pid in filtered}

            now = _now_iso()
            for pid, fields in filtered.items():
                row = next(
                    (r for r in data.get("positions", []) if r.get("position_id") == pid),
                    None,
                )
                if row is None:
                    outcome[pid] = "skipped:not_found"
                    continue
                if row.get("status") != "open":
                    # A concurrent writer closed it (or it's partial_exit/closing
                    # — those are not for the watcher to mutate either).
                    outcome[pid] = f"skipped:not_open:{row.get('status')}"
                    continue

                touched = False
                for key, val in fields.items():
                    serialised = _coerce_for_disk(val)
                    if key == "max_favorable_pnl":
                        # Ratchet UP only — never lower a previously-recorded MFE.
                        prev = _decimal_or_zero(row.get("max_favorable_pnl"))
                        new_d = _decimal_or_zero(serialised)
                        if new_d > prev:
                            row["max_favorable_pnl"] = str(serialised)
                            touched = True
                    elif key == "max_adverse_pnl":
                        # Ratchet DOWN only — never raise a previously-recorded MAE.
                        prev = _decimal_or_zero(row.get("max_adverse_pnl"))
                        new_d = _decimal_or_zero(serialised)
                        if new_d < prev:
                            row["max_adverse_pnl"] = str(serialised)
                            touched = True
                    elif key == "notes":
                        # Append new notes; never replace the existing list.
                        # Deduplicate against the most recent few entries so
                        # repeated ticks don't spam the same line.
                        existing = list(row.get("notes") or [])
                        new_notes = list(val) if isinstance(val, list) else [str(val)]
                        tail = set(existing[-10:])
                        for n in new_notes:
                            if n not in tail:
                                existing.append(n)
                                tail.add(n)
                                touched = True
                        row["notes"] = existing
                    elif key == "updated_at":
                        # Always allowed, but only if something else was touched
                        # this call — we don't want to bump updated_at on
                        # every no-op tick.
                        continue
                    else:
                        # unrealized_pnl and any other future whitelisted scalar
                        row[key] = str(serialised) if isinstance(serialised, Decimal) else serialised
                        touched = True

                if touched:
                    row["updated_at"] = now
                    outcome[pid] = "merged"
                else:
                    outcome[pid] = "skipped:no_change"

            # last_reconciled_at is set by save_all() callers, NOT by the
            # watcher — leave it untouched here so concurrent reconciliation
            # writes are visible. We only refresh it if it's missing.
            data.setdefault("last_reconciled_at", _now_iso())
            self._atomic_write(json.dumps(data, indent=2))
        return outcome

    def remove_closed(self, *, keep_last_n: int | None = None) -> int:
        """Drop closed positions from the file.

        Optionally keep the last ``keep_last_n`` closed positions for context;
        the rest are pruned (already journaled, so no information loss).

        Returns the number removed.
        """
        with self._file_lock():
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
            self._save_all_locked(new_all)
            return removed

    # ----- internals ---------------------------------------------------

    @contextlib.contextmanager
    def _file_lock(self):
        """Process-level exclusive lock for read-modify-write cycles.

        Held over the lock-file at ``<path>.lock`` so the canonical JSON
        file's inode is free to be renamed atomically. ``fcntl.flock`` is
        advisory on POSIX but every writer in this codebase routes through
        ``PositionsStore`` — concurrent ``run_full_auto_cycle``, watcher,
        PnL auto-adjust monitor, reconciliation scripts, and emergency
        scripts all serialise on this single lock.

        Falls back to a no-op on platforms without ``fcntl`` (Windows).
        Tests on POSIX exercise the real lock; the no-op path is acceptable
        because Windows is not a supported live-trading environment for
        this project.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        if not _HAS_FCNTL:
            yield
            return
        # Open the lock file (creating it if absent) and take an exclusive
        # blocking lock. The fd is closed in the finally, which releases
        # the lock per fcntl semantics.
        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

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


def _coerce_for_disk(v: Any) -> Any:
    """Normalise watcher field values to the on-disk str-for-Decimal shape."""
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int, float)):
        # Accept floats for convenience but stringify via Decimal to avoid
        # 0.1 + 0.2 drift. Watcher callers should already pass Decimal.
        return Decimal(str(v))
    return v


def _decimal_or_zero(v: Any) -> Decimal:
    if v is None or v == "":
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


__all__ = [
    "Position",
    "PositionsStore",
    "OPEN_POSITIONS",
    "VALID_STATUSES",
    "WATCHER_ALLOWED_FIELDS",
    "make_position_id",
]
