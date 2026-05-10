"""Live smoke tests against Binance public API.

These hit the real exchange — opt-in via env var so they don't run in CI by
accident. Run with::

    BINANCE_LIVE_TESTS=1 python -m pytest tests/test_smoke_live.py -v
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

from scripts.binance_client import BinanceClient
from scripts.market_data import MarketData
from scripts.symbol_filters import parse_exchange_info

LIVE = os.environ.get("BINANCE_LIVE_TESTS") == "1"
pytestmark = pytest.mark.skipif(not LIVE, reason="set BINANCE_LIVE_TESTS=1 to run")


@pytest.fixture(scope="module")
def market() -> MarketData:
    return MarketData(BinanceClient())


def test_exchange_info_has_btcusdt(market: MarketData):
    info = market.get_exchange_info()
    specs = parse_exchange_info(info)
    assert "BTCUSDT" in specs
    btc = specs["BTCUSDT"]
    assert btc.is_perpetual
    assert btc.is_usdt_quoted


def test_klines_btcusdt_returns_candles(market: MarketData):
    candles = market.get_klines("BTCUSDT", "1h", limit=5)
    assert len(candles) == 5
    last = candles[-1]
    assert last.high >= last.low > 0
    assert last.quote_volume >= 0


def test_ticker_btcusdt_has_price(market: MarketData):
    t = market.get_ticker_24h("BTCUSDT")
    assert t.last_price > 0
    assert t.quote_volume > 0


def test_premium_index_btcusdt_has_funding(market: MarketData):
    m = market.get_mark_price("BTCUSDT")
    assert m.mark_price > 0
    # funding rate is a small fraction; |x| < 5% sanity
    assert abs(m.last_funding_rate) < Decimal("0.05")


def test_depth_btcusdt_spread_is_tight(market: MarketData):
    book = market.get_order_book("BTCUSDT", limit=20)
    assert book.best_bid is not None and book.best_ask is not None
    bps = book.spread_bps
    assert bps is not None
    # BTC spread is typically <2 bps; allow up to 20 bps for safety.
    assert bps < Decimal("20")
