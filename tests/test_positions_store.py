"""Positions store: atomic write + lifecycle correctness."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.positions_store import (
    Position, PositionsStore, make_position_id,
)


def _make(symbol: str = "DOGEUSDT", side: str = "LONG", status: str = "open",
          qty: str = "100", entry: str = "0.07654") -> Position:
    return Position(
        position_id=make_position_id(symbol),
        symbol=symbol, side=side, status=status,
        entry_price=Decimal(entry),
        quantity=Decimal(qty), initial_quantity=Decimal(qty),
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2"), notional_usdt=Decimal("7.654"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800"), Decimal("0.08000")],
        unrealized_pnl=Decimal("0"), realized_pnl=Decimal("-0.005"),
        max_favorable_pnl=Decimal("0"), max_adverse_pnl=Decimal("0"),
        liquidation_price=Decimal("0.05100"),
        fees_paid_usdt=Decimal("0.005"), funding_paid_usdt=Decimal("0"),
        proposal_id="PROP-test-001",
        strategy="pullback_long", market_regime="bullish",
        opened_at="2026-05-10T12:00:00Z", updated_at="2026-05-10T12:00:00Z",
        closed_at=None, exit_price=None, exit_reason=None, mode="PAPER_TRADING",
    )


def test_roundtrip_position(tmp_path: Path):
    store = PositionsStore(tmp_path / "open-positions.json")
    p = _make()
    store.upsert(p)
    loaded = store.find(p.position_id)
    assert loaded is not None
    assert loaded.symbol == p.symbol
    assert loaded.entry_price == p.entry_price
    assert loaded.take_profit_targets == p.take_profit_targets


def test_load_open_filters_closed(tmp_path: Path):
    store = PositionsStore(tmp_path / "open-positions.json")
    store.upsert(_make(symbol="DOGEUSDT", status="open"))
    store.upsert(_make(symbol="SHIBUSDT", status="closed"))
    open_only = store.load_open()
    assert len(open_only) == 1
    assert open_only[0].symbol == "DOGEUSDT"


def test_atomic_write_no_partial_file(tmp_path: Path):
    store = PositionsStore(tmp_path / "open-positions.json")
    store.upsert(_make())
    # The temp file must not linger after a successful write.
    leftover = list((tmp_path).glob(".tmp.*"))
    assert leftover == []
    # The canonical file must be valid JSON.
    data = json.loads((tmp_path / "open-positions.json").read_text())
    assert "positions" in data and len(data["positions"]) == 1


def test_mark_to_market_long():
    p = _make()
    pnl = p.mark_to_market(Decimal("0.07700"))
    # (0.07700 - 0.07654) * 100 = 0.046
    assert pnl == pytest.approx(Decimal("0.046"), abs=Decimal("0.0001"))


def test_mark_to_market_short():
    p = _make(side="SHORT")
    pnl = p.mark_to_market(Decimal("0.07500"))
    # (0.07654 - 0.07500) * 100 = 0.154
    assert pnl == pytest.approx(Decimal("0.154"), abs=Decimal("0.0001"))


def test_update_pnl_tracks_mfe_mae():
    p = _make()
    p.update_pnl(Decimal("0.07700"))
    assert p.max_favorable_pnl > 0
    p.update_pnl(Decimal("0.07550"))      # adverse
    assert p.max_adverse_pnl < 0
    # MFE must persist after subsequent adverse moves.
    assert p.max_favorable_pnl > 0


def test_remove_closed_keeps_open(tmp_path: Path):
    store = PositionsStore(tmp_path / "open-positions.json")
    store.upsert(_make(symbol="A", status="open"))
    closed = _make(symbol="B", status="closed")
    closed.closed_at = "2026-05-10T13:00:00Z"
    store.upsert(closed)
    removed = store.remove_closed()
    assert removed == 1
    rest = store.load_all()
    assert len(rest) == 1 and rest[0].symbol == "A"


# ----------------------------------------------------------------------------
# Watcher-clobber race regression tests (memory/execution-errors.md
# ERROR-20260511-6). The watcher must NEVER overwrite fields outside the
# whitelist, even when another writer raced ahead of it.
# ----------------------------------------------------------------------------


def test_apply_watcher_updates_does_not_clobber_stop_loss(tmp_path: Path):
    """A concurrent writer's new stop_loss must survive a watcher update."""
    store = PositionsStore(tmp_path / "open-positions.json")
    p = _make(symbol="BUSDT")
    store.upsert(p)

    # Concurrent writer (e.g. emergency_close or operator script) updates
    # stop_loss directly in the JSON. Watcher then arrives with its own
    # tick.
    raw = json.loads((tmp_path / "open-positions.json").read_text())
    raw["positions"][0]["stop_loss"] = "0.4514"
    raw["positions"][0]["algo_order_ids"] = {"sl": "NEW-ALGO-ID-9999"}
    (tmp_path / "open-positions.json").write_text(json.dumps(raw, indent=2))

    outcome = store.apply_watcher_updates({
        p.position_id: {
            "unrealized_pnl": Decimal("0.5"),
            "max_favorable_pnl": Decimal("0.5"),
            "stop_loss": Decimal("999.0"),                # MUST be dropped
            "algo_order_ids": {"sl": "OLD-ALGO-ID-1111"}, # MUST be dropped
            "status": "closed",                            # MUST be dropped
        },
    })
    assert outcome[p.position_id] == "merged"

    after = json.loads((tmp_path / "open-positions.json").read_text())
    row = after["positions"][0]
    # Concurrent writer's values must be preserved.
    assert row["stop_loss"] == "0.4514"
    assert row["algo_order_ids"] == {"sl": "NEW-ALGO-ID-9999"}
    assert row["status"] == "open"
    # Whitelisted fields were applied.
    assert row["unrealized_pnl"] == "0.5"
    assert row["max_favorable_pnl"] == "0.5"


def test_apply_watcher_updates_ratchets_mfe_up_only(tmp_path: Path):
    store = PositionsStore(tmp_path / "open-positions.json")
    p = _make(symbol="A")
    p.max_favorable_pnl = Decimal("1.50")
    store.upsert(p)

    # A stale tick tries to LOWER max_favorable_pnl — must be ignored.
    outcome = store.apply_watcher_updates({
        p.position_id: {"max_favorable_pnl": Decimal("0.20")},
    })
    assert outcome[p.position_id] in ("skipped:no_change", "merged")
    row = json.loads((tmp_path / "open-positions.json").read_text())["positions"][0]
    assert row["max_favorable_pnl"] == "1.50"

    # A higher tick must take effect.
    store.apply_watcher_updates({
        p.position_id: {"max_favorable_pnl": Decimal("2.00")},
    })
    row = json.loads((tmp_path / "open-positions.json").read_text())["positions"][0]
    assert row["max_favorable_pnl"] == "2.00"


def test_apply_watcher_updates_ratchets_mae_down_only(tmp_path: Path):
    store = PositionsStore(tmp_path / "open-positions.json")
    p = _make(symbol="A")
    p.max_adverse_pnl = Decimal("-1.50")
    store.upsert(p)

    # A stale tick tries to RAISE max_adverse_pnl (less adverse) — ignored.
    store.apply_watcher_updates({
        p.position_id: {"max_adverse_pnl": Decimal("-0.20")},
    })
    row = json.loads((tmp_path / "open-positions.json").read_text())["positions"][0]
    assert row["max_adverse_pnl"] == "-1.50"

    # A more-adverse tick must take effect.
    store.apply_watcher_updates({
        p.position_id: {"max_adverse_pnl": Decimal("-2.00")},
    })
    row = json.loads((tmp_path / "open-positions.json").read_text())["positions"][0]
    assert row["max_adverse_pnl"] == "-2.00"


def test_apply_watcher_updates_skips_non_open(tmp_path: Path):
    store = PositionsStore(tmp_path / "open-positions.json")
    p = _make(symbol="A", status="open")
    store.upsert(p)
    # Concurrent writer closes the position before the watcher's flush.
    raw = json.loads((tmp_path / "open-positions.json").read_text())
    raw["positions"][0]["status"] = "closed"
    raw["positions"][0]["closed_at"] = "2026-05-11T11:00:00Z"
    raw["positions"][0]["exit_price"] = "0.07700"
    (tmp_path / "open-positions.json").write_text(json.dumps(raw, indent=2))

    outcome = store.apply_watcher_updates({
        p.position_id: {"unrealized_pnl": Decimal("0.5")},
    })
    assert outcome[p.position_id].startswith("skipped:not_open")
    row = json.loads((tmp_path / "open-positions.json").read_text())["positions"][0]
    # Concurrent close survived.
    assert row["status"] == "closed"
    assert row["closed_at"] == "2026-05-11T11:00:00Z"
    # Watcher's unrealized_pnl was NOT applied.
    assert row["unrealized_pnl"] == "0"


def test_apply_watcher_updates_skips_missing_position(tmp_path: Path):
    store = PositionsStore(tmp_path / "open-positions.json")
    store.upsert(_make(symbol="A"))
    outcome = store.apply_watcher_updates({
        "POS-bogus-id": {"unrealized_pnl": Decimal("0.5")},
    })
    assert outcome["POS-bogus-id"] == "skipped:not_found"


def test_apply_watcher_updates_preserves_unknown_fields(tmp_path: Path):
    """Forward-compat fields on disk (e.g. planned_loss_at_sl_usdt_initial)
    must survive a watcher merge — apply_watcher_updates writes back the
    raw row, not a deserialised Position."""
    store = PositionsStore(tmp_path / "open-positions.json")
    p = _make(symbol="A")
    store.upsert(p)
    raw = json.loads((tmp_path / "open-positions.json").read_text())
    raw["positions"][0]["planned_loss_at_sl_usdt_initial"] = "0.42"
    raw["positions"][0]["custom_future_field"] = "operator note"
    (tmp_path / "open-positions.json").write_text(json.dumps(raw, indent=2))

    store.apply_watcher_updates({
        p.position_id: {"unrealized_pnl": Decimal("0.1")},
    })
    after = json.loads((tmp_path / "open-positions.json").read_text())["positions"][0]
    assert after["planned_loss_at_sl_usdt_initial"] == "0.42"
    assert after["custom_future_field"] == "operator note"
    assert after["unrealized_pnl"] == "0.1"


def test_apply_watcher_updates_appends_notes(tmp_path: Path):
    store = PositionsStore(tmp_path / "open-positions.json")
    p = _make(symbol="A")
    p.notes = ["original note 1"]
    store.upsert(p)
    store.apply_watcher_updates({
        p.position_id: {"notes": ["watcher note A", "watcher note B"]},
    })
    after = json.loads((tmp_path / "open-positions.json").read_text())["positions"][0]
    assert after["notes"] == ["original note 1", "watcher note A", "watcher note B"]


def test_apply_watcher_updates_empty_input_is_noop(tmp_path: Path):
    store = PositionsStore(tmp_path / "open-positions.json")
    store.upsert(_make(symbol="A"))
    assert store.apply_watcher_updates({}) == {}
    # File still valid.
    data = json.loads((tmp_path / "open-positions.json").read_text())
    assert len(data["positions"]) == 1
