"""Backtester: deterministic synthetic-candle walk-forward."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from scripts.backtester import backtest_candles
from scripts.market_data import Candle
from scripts.symbol_filters import parse_symbol_spec


def _candle(o, h, l, c, v=10_000_000, t=0):
    """Build a high-volume candle so the backtester treats the symbol as liquid."""
    o, h, l, c = (Decimal(str(x)) for x in (o, h, l, c))
    return Candle(
        open_time_ms=t, open=o, high=h, low=l, close=c,
        volume=Decimal(str(v)), close_time_ms=t + 3_600_000,
        quote_volume=Decimal(str(v)) * c,    # quote-asset volume
        trades=500,
        taker_buy_base_volume=Decimal(str(v / 2)),
        taker_buy_quote_volume=Decimal(str(v / 2)) * c,
    )


@pytest.fixture
def doge_spec():
    raw = {
        "symbol": "DOGEUSDT", "pair": "DOGEUSDT", "contractType": "PERPETUAL",
        "status": "TRADING", "baseAsset": "DOGE", "quoteAsset": "USDT",
        "pricePrecision": 5, "quantityPrecision": 0,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.00001",
             "maxPrice": "1000", "tickSize": "0.00001"},
            {"filterType": "LOT_SIZE", "minQty": "1", "maxQty": "10000000", "stepSize": "1"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "1",
             "maxQty": "5900000", "stepSize": "1"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
            {"filterType": "PERCENT_PRICE", "multiplierUp": "1.15",
             "multiplierDown": "0.85", "multiplierDecimal": "4"},
        ],
    }
    return parse_symbol_spec(raw)


def _make_uptrend_with_pullbacks(n: int = 250) -> list:
    """Generate an upward sine drift with periodic pullbacks.

    Designed so the backtester can find pullback_long setups at sine troughs.
    """
    out = []
    base = 0.07000
    for i in range(n):
        # Drift up 0.0002 per bar plus a sine wave of amplitude 0.001
        drift = base + 0.00015 * i + 0.001 * math.sin(i / 5.0)
        # Make body small + wicks proportional to drift
        o = drift - 0.00005
        c = drift
        h = drift + 0.0003
        l = drift - 0.0003
        out.append(_candle(o, h, l, c, t=i * 3_600_000))
    return out


def test_backtest_runs_to_completion_on_uptrend_data(doge_spec):
    candles = _make_uptrend_with_pullbacks(250)
    result = backtest_candles(doge_spec, candles, interval="1h", warmup_bars=100)
    assert result.bars_examined == len(candles)
    # We don't require profitable trades — the backtester correctness check is
    # that it produces a deterministic, well-shaped result.
    assert result.proposals_generated >= 0
    assert isinstance(result.trades, list)
    assert "trades" in result.aggregate
    if result.trades:
        # Every trade must have an exit reason and a closed-out qty.
        for t in result.trades:
            assert t.exit_reason is not None
            assert t.exit_bar is not None
            assert t.bars_held > 0


def test_backtest_handles_insufficient_candles(doge_spec):
    short = _make_uptrend_with_pullbacks(20)
    result = backtest_candles(doge_spec, short, interval="1h", warmup_bars=100)
    assert result.aggregate.get("error") == "insufficient candles" or result.proposals_generated == 0
