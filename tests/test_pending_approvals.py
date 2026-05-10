"""Pending approvals store: lifecycle + atomic ops."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.pending_approvals import (
    PendingApproval,
    PendingApprovalsStore,
    default_deadline_iso,
    make_approval_id,
)


def _make(symbol: str = "DOGEUSDT",
          deadline_at: str | None = None,
          notional: str = "75") -> PendingApproval:
    return PendingApproval(
        approval_id=make_approval_id(symbol),
        proposal_id="PROP-1",
        symbol=symbol, side="LONG", strategy="pullback_long",
        entry_price=Decimal("0.07654"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800"), Decimal("0.07900")],
        quantity=Decimal("980"),
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("25"),
        notional_usdt=Decimal(notional),
        estimated_fees_usdt=Decimal("0.0375"),
        liquidation_price=Decimal("0.05100"),
        requires_approval_reason="notional 75 USDT > threshold 50 USDT",
        triggered_rules=["notional_above_threshold"],
        created_at="2026-05-10T14:00:00Z",
        deadline_at=deadline_at or default_deadline_iso(hours_from_now=1),
    )


def test_roundtrip(tmp_path: Path):
    store = PendingApprovalsStore(tmp_path / "pending.json")
    a = _make()
    store.upsert(a)
    loaded = store.find(a.approval_id)
    assert loaded is not None
    assert loaded.entry_price == a.entry_price
    assert loaded.take_profit_targets == a.take_profit_targets
    assert loaded.status == "pending"


def test_load_pending_filters(tmp_path: Path):
    store = PendingApprovalsStore(tmp_path / "pending.json")
    a1 = _make(symbol="DOGEUSDT")
    a2 = _make(symbol="SHIBUSDT")
    store.upsert(a1)
    store.upsert(a2)
    store.transition(a2.approval_id, to="approved", notes="test")
    pending = store.load_pending()
    assert len(pending) == 1
    assert pending[0].symbol == "DOGEUSDT"
    actionable = store.load_actionable()
    assert len(actionable) == 1
    assert actionable[0].symbol == "SHIBUSDT"


def test_lifecycle_transitions(tmp_path: Path):
    store = PendingApprovalsStore(tmp_path / "pending.json")
    a = _make()
    store.upsert(a)
    # pending → approved
    store.transition(a.approval_id, to="approved", notes="user said yes")
    after = store.find(a.approval_id)
    assert after.status == "approved"
    assert after.decision_notes == "user said yes"
    assert after.decided_at is not None
    # approved → executed
    store.transition(a.approval_id, to="executed", notes="filled",
                     executed_order_id=42, executed_avg_price=Decimal("0.07655"))
    after = store.find(a.approval_id)
    assert after.status == "executed"
    assert after.executed_order_id == 42
    assert after.executed_avg_price == Decimal("0.07655")
    assert after.is_terminal


def test_invalid_transition_raises(tmp_path: Path):
    store = PendingApprovalsStore(tmp_path / "pending.json")
    a = _make()
    store.upsert(a)
    with pytest.raises(ValueError):
        store.transition(a.approval_id, to="bogus")


def test_expire_overdue(tmp_path: Path):
    store = PendingApprovalsStore(tmp_path / "pending.json")
    past = (dt.datetime.utcnow() - dt.timedelta(hours=1)).isoformat(timespec="seconds") + "Z"
    a_old = _make(symbol="OLDUSDT", deadline_at=past)
    a_new = _make(symbol="NEWUSDT")    # default: deadline in 1h
    store.upsert(a_old)
    store.upsert(a_new)
    n = store.expire_overdue()
    assert n == 1
    expired = store.find(a_old.approval_id)
    assert expired.status == "expired"
    fresh = store.find(a_new.approval_id)
    assert fresh.status == "pending"


def test_prune_terminal_keeps_open_and_recent_terminal(tmp_path: Path):
    store = PendingApprovalsStore(tmp_path / "pending.json")
    pending = _make(symbol="OPENUSDT")
    store.upsert(pending)
    # Add 5 terminal entries.
    for i in range(5):
        a = _make(symbol=f"DONE{i}USDT")
        store.upsert(a)
        store.transition(a.approval_id, to="executed", notes="t")
    # Prune to keep last 2 terminal.
    removed = store.prune_terminal(keep_last_n=2)
    assert removed == 3
    rest = store.load_all()
    # 1 open + 2 terminal kept = 3 total
    assert len(rest) == 3
    assert any(p.status == "pending" for p in rest)


def test_atomic_write_no_leftover_tmp(tmp_path: Path):
    store = PendingApprovalsStore(tmp_path / "pending.json")
    store.upsert(_make())
    leftovers = list(tmp_path.glob(".tmp.*"))
    assert leftovers == []


def test_is_expired_helper():
    past = (dt.datetime.utcnow() - dt.timedelta(minutes=1)).isoformat(timespec="seconds") + "Z"
    future = (dt.datetime.utcnow() + dt.timedelta(hours=1)).isoformat(timespec="seconds") + "Z"
    assert _make(deadline_at=past).is_expired()
    assert not _make(deadline_at=future).is_expired()
