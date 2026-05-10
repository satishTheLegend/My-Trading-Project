"""Paper execution: depth-aware fill simulator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.market_data import OrderBook, OrderBookLevel
from scripts.paper_execution import simulate_limit_fill, simulate_market_fill


def _book(bids, asks, symbol="DOGEUSDT") -> OrderBook:
    return OrderBook(
        symbol=symbol,
        last_update_id=1,
        bids=tuple(OrderBookLevel(price=Decimal(str(p)), quantity=Decimal(str(q))) for p, q in bids),
        asks=tuple(OrderBookLevel(price=Decimal(str(p)), quantity=Decimal(str(q))) for p, q in asks),
        transaction_time_ms=1,
    )


def test_market_long_walks_asks():
    book = _book(
        bids=[("0.07650", "1000"), ("0.07649", "5000")],
        asks=[("0.07655", "100"), ("0.07656", "200"), ("0.07658", "10000")],
    )
    fill = simulate_market_fill("LONG", Decimal("250"), book)
    assert fill.is_complete
    assert fill.filled_qty == Decimal("250")
    # 100 @ 0.07655 + 150 @ 0.07656 → VWAP = (7.655 + 11.484) / 250 = 0.076556
    assert fill.average_price == pytest.approx(Decimal("0.076556"), abs=Decimal("0.000005"))
    assert fill.levels_consumed == 2


def test_market_short_walks_bids():
    book = _book(
        bids=[("0.07650", "100"), ("0.07648", "200"), ("0.07645", "5000")],
        asks=[("0.07655", "100")],
    )
    fill = simulate_market_fill("SHORT", Decimal("250"), book)
    assert fill.is_complete
    # 100 @ 0.07650 + 150 @ 0.07648
    assert fill.average_price == pytest.approx(Decimal("0.076488"), abs=Decimal("0.000005"))
    assert fill.levels_consumed == 2


def test_partial_fill_when_book_thin():
    book = _book(
        bids=[("0.07650", "10")],
        asks=[("0.07655", "10"), ("0.07656", "5")],
    )
    fill = simulate_market_fill("LONG", Decimal("100"), book)
    assert not fill.is_complete
    assert fill.filled_qty == Decimal("15")
    assert "partial fill" in fill.notes or "exhausted" in fill.notes


def test_empty_book_returns_zero_fill():
    book = _book(bids=[], asks=[])
    fill = simulate_market_fill("LONG", Decimal("10"), book)
    assert fill.filled_qty == 0
    assert fill.is_complete is False


def test_limit_long_fills_only_eligible_levels():
    book = _book(
        bids=[("0.07650", "100")],
        asks=[("0.07655", "100"), ("0.07700", "1000")],
    )
    # Limit at 0.07660 — only the 0.07655 level qualifies (≤ 0.07660).
    fill = simulate_limit_fill("LONG", Decimal("200"), Decimal("0.07660"), book)
    assert fill.filled_qty == Decimal("100")          # only the eligible level
    assert fill.is_complete is False
    assert "rest on book" in fill.notes or "remainder unfilled" in fill.notes


def test_limit_no_cross_returns_unfilled():
    book = _book(
        bids=[("0.07650", "100")],
        asks=[("0.07700", "100")],
    )
    fill = simulate_limit_fill("LONG", Decimal("50"), Decimal("0.07660"), book)
    assert fill.filled_qty == 0
    assert fill.is_complete is False
    assert "limit price not crossed" in fill.notes


def test_invalid_inputs():
    book = _book(bids=[("1", "1")], asks=[("2", "1")])
    with pytest.raises(ValueError):
        simulate_market_fill("HEDGE", Decimal("1"), book)
    with pytest.raises(ValueError):
        simulate_market_fill("LONG", Decimal("0"), book)


def test_slippage_bps_is_nonzero_when_walking_book():
    book = _book(
        bids=[("0.07650", "100")],
        asks=[("0.07655", "100"), ("0.07660", "100")],
    )
    fill = simulate_market_fill("LONG", Decimal("150"), book)
    # Mid is (0.07650+0.07655)/2 = 0.076525. Avg fill is above mid → +ve bps.
    assert fill.slippage_bps > 0
