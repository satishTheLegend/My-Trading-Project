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
