"""Pending-approvals store — disk-backed queue of trades waiting for the
user's explicit OK.

Backs ``data/pending-approvals.json``. Same atomic-write discipline as
``positions_store.py``: write to a sibling temp file, then ``os.replace`` so
a crash mid-write never corrupts the canonical file.

Lifecycle::

    pending  → approved  → executed
             → rejected
             → expired   (deadline passed without action)
             → cancelled (user explicitly removed from queue)

Approved entries stay in the file until the live cycle picks them up and
flips them to ``executed``. The ``run_approvals.py --clean`` CLI prunes
terminal entries (executed / rejected / expired / cancelled) to keep the
file small.
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
PENDING_APPROVALS = _PROJECT_ROOT / "data" / "pending-approvals.json"

VALID_STATUSES = ("pending", "approved", "rejected", "expired", "executed", "cancelled")


@dataclass
class PendingApproval:
    """One queued proposal."""

    approval_id: str
    proposal_id: str
    symbol: str
    side: str
    strategy: str
    entry_price: Decimal
    stop_loss: Decimal
    take_profit_targets: list[Decimal]
    quantity: Decimal
    leverage: int
    margin_mode: str
    margin_usdt: Decimal
    notional_usdt: Decimal
    estimated_fees_usdt: Decimal
    liquidation_price: Decimal | None
    requires_approval_reason: str
    triggered_rules: list[str]
    created_at: str
    deadline_at: str
    status: str = "pending"
    decided_at: str | None = None
    decision_notes: str = ""
    executed_order_id: int | None = None
    executed_avg_price: Decimal | None = None

    # ------- helpers -------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        return self.status in ("executed", "rejected", "expired", "cancelled")

    @property
    def is_actionable(self) -> bool:
        """True if a worker should pick this up next tick."""
        return self.status == "approved"

    def is_expired(self, now: dt.datetime | None = None) -> bool:
        now = now or dt.datetime.utcnow()
        try:
            deadline = dt.datetime.fromisoformat(self.deadline_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            return False
        if deadline.tzinfo is None:
            return now > deadline
        return now.replace(tzinfo=deadline.tzinfo) > deadline

    # ------- serdes --------------------------------------------------

    def to_jsonable(self) -> dict[str, Any]:
        d = asdict(self)
        for k, v in list(d.items()):
            if isinstance(v, Decimal):
                d[k] = str(v)
            elif isinstance(v, list) and v and isinstance(v[0], Decimal):
                d[k] = [str(x) for x in v]
        if d.get("liquidation_price") is None:
            d["liquidation_price"] = None
        if d.get("executed_avg_price") is None:
            d["executed_avg_price"] = None
        return d

    @classmethod
    def from_jsonable(cls, d: dict[str, Any]) -> "PendingApproval":
        kw: dict[str, Any] = {}
        decimal_fields = {
            "entry_price", "stop_loss", "quantity", "margin_usdt",
            "notional_usdt", "estimated_fees_usdt",
        }
        nullable_decimal_fields = {"liquidation_price", "executed_avg_price"}
        for k, v in d.items():
            if k in decimal_fields:
                kw[k] = Decimal(str(v))
            elif k in nullable_decimal_fields:
                kw[k] = Decimal(str(v)) if v not in (None, "", "null") else None
            elif k == "take_profit_targets":
                kw[k] = [Decimal(str(x)) for x in (v or [])]
            elif k == "leverage":
                kw[k] = int(v)
            else:
                kw[k] = v
        kw.setdefault("triggered_rules", [])
        kw.setdefault("decision_notes", "")
        return cls(**kw)


# ----------------------------------------------------------------------------
# Store
# ----------------------------------------------------------------------------


class PendingApprovalsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PENDING_APPROVALS

    # ----- read --------------------------------------------------------

    def load_all(self) -> list[PendingApproval]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        out: list[PendingApproval] = []
        for raw in data.get("approvals", []):
            try:
                out.append(PendingApproval.from_jsonable(raw))
            except Exception:
                continue
        return out

    def load_pending(self) -> list[PendingApproval]:
        return [a for a in self.load_all() if a.status == "pending"]

    def load_actionable(self) -> list[PendingApproval]:
        return [a for a in self.load_all() if a.is_actionable]

    def find(self, approval_id: str) -> PendingApproval | None:
        for a in self.load_all():
            if a.approval_id == approval_id:
                return a
        return None

    # ----- write -------------------------------------------------------

    def save_all(self, approvals: Iterable[PendingApproval]) -> None:
        data = {
            "approvals": [a.to_jsonable() for a in approvals],
            "updated_at": _now_iso(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(json.dumps(data, indent=2))

    def upsert(self, approval: PendingApproval) -> None:
        all_a = self.load_all()
        idx = next((i for i, a in enumerate(all_a) if a.approval_id == approval.approval_id), None)
        if idx is None:
            all_a.append(approval)
        else:
            all_a[idx] = approval
        self.save_all(all_a)

    def transition(
        self, approval_id: str, *, to: str, notes: str = "",
        executed_order_id: int | None = None,
        executed_avg_price: Decimal | None = None,
    ) -> PendingApproval | None:
        if to not in VALID_STATUSES:
            raise ValueError(f"invalid status {to!r}")
        all_a = self.load_all()
        for a in all_a:
            if a.approval_id != approval_id:
                continue
            a.status = to
            a.decided_at = _now_iso()
            if notes:
                a.decision_notes = notes
            if executed_order_id is not None:
                a.executed_order_id = executed_order_id
            if executed_avg_price is not None:
                a.executed_avg_price = executed_avg_price
            self.save_all(all_a)
            return a
        return None

    def expire_overdue(self, now: dt.datetime | None = None) -> int:
        """Mark every pending approval past its deadline as ``expired``.
        Returns the count expired.
        """
        now = now or dt.datetime.utcnow()
        all_a = self.load_all()
        n = 0
        for a in all_a:
            if a.status == "pending" and a.is_expired(now):
                a.status = "expired"
                a.decided_at = _now_iso()
                a.decision_notes = "deadline passed without action"
                n += 1
        if n:
            self.save_all(all_a)
        return n

    def prune_terminal(self, *, keep_last_n: int = 50) -> int:
        """Drop oldest terminal entries, keeping the most recent N.
        Returns the count removed.
        """
        all_a = self.load_all()
        non_term = [a for a in all_a if not a.is_terminal]
        term = sorted(
            (a for a in all_a if a.is_terminal),
            key=lambda a: a.decided_at or "",
            reverse=True,
        )
        keep = term[:keep_last_n]
        new_all = non_term + keep
        removed = len(all_a) - len(new_all)
        if removed:
            self.save_all(new_all)
        return removed

    # ----- internals ---------------------------------------------------

    def _atomic_write(self, content: str) -> None:
        d = self.path.parent
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=d, prefix=".tmp.", delete=False,
        ) as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self.path)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def make_approval_id(symbol: str, when: dt.datetime | None = None, seq: int = 1) -> str:
    when = when or dt.datetime.utcnow()
    return f"APRV-{when:%Y%m%d-%H%M%S}-{symbol}-{seq:03d}"


def default_deadline_iso(*, hours_from_now: float = 1.0) -> str:
    deadline = dt.datetime.utcnow() + dt.timedelta(hours=hours_from_now)
    return deadline.isoformat(timespec="seconds") + "Z"


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


__all__ = [
    "PendingApproval",
    "PendingApprovalsStore",
    "PENDING_APPROVALS",
    "VALID_STATUSES",
    "make_approval_id",
    "default_deadline_iso",
]
