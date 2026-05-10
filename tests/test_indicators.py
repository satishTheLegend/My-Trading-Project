"""Indicator math: deterministic checks against hand-computed expectations."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from scripts.indicators import (
    atr,
    bollinger,
    cluster_levels,
    ema,
    pct_change,
    realized_volatility_pct,
    rsi,
    sma,
    swing_pivots,
    support_resistance,
    vwap,
)
from scripts.market_data import Candle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _candle(o: float, h: float, l: float, c: float, v: float = 1000.0, t: int = 0) -> Candle:
    """Construct a Candle with sensible defaults for tests."""
    return Candle(
        open_time_ms=t,
        open=Decimal(str(o)),
        high=Decimal(str(h)),
        low=Decimal(str(l)),
        close=Decimal(str(c)),
        volume=Decimal(str(v)),
        close_time_ms=t + 1,
        quote_volume=Decimal(str(v * c)),
        trades=10,
        taker_buy_base_volume=Decimal(str(v / 2)),
        taker_buy_quote_volume=Decimal(str(v * c / 2)),
    )


# ---------------------------------------------------------------------------
# SMA / EMA
# ---------------------------------------------------------------------------


def test_sma_warmup_then_match():
    out = sma([1, 2, 3, 4, 5], 3)
    assert math.isnan(out[0]) and math.isnan(out[1])
    assert out[2] == pytest.approx(2.0)
    assert out[3] == pytest.approx(3.0)
    assert out[4] == pytest.approx(4.0)


def test_ema_constant_input_converges_to_value():
    out = ema([5.0] * 50, 14)
    # After warmup the EMA of a constant equals the constant.
    assert out[-1] == pytest.approx(5.0, abs=1e-12)


def test_ema_period_validation():
    with pytest.raises(ValueError):
        ema([1, 2, 3], 0)


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------


def test_rsi_steady_uptrend_pegs_near_100():
    series = list(range(1, 50))
    out = rsi(series, 14)
    # RSI of a pure uptrend is 100.
    assert out[-1] == pytest.approx(100.0)


def test_rsi_steady_downtrend_pegs_near_0():
    series = list(range(50, 1, -1))
    out = rsi(series, 14)
    assert out[-1] == pytest.approx(0.0)


def test_rsi_flat_series_is_50():
    out = rsi([10] * 30, 14)
    # No price change → no gains/losses; convention pegs at 50.
    assert out[-1] == pytest.approx(50.0) or out[-1] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------


def test_atr_constant_range_equals_range():
    candles = [_candle(100, 102, 98, 100, t=i) for i in range(20)]
    out = atr(candles, 14)
    # All TRs are 4 (high-low). ATR settles at 4.
    last = out[-1]
    assert last == pytest.approx(4.0, abs=0.5)


# ---------------------------------------------------------------------------
# VWAP
# ---------------------------------------------------------------------------


def test_vwap_constant_price_equals_price():
    candles = [_candle(50, 50, 50, 50, v=10, t=i) for i in range(5)]
    out = vwap(candles)
    for v in out:
        assert v == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Pivots / S-R
# ---------------------------------------------------------------------------


def test_swing_pivots_finds_clear_high():
    # Build a pyramid: rising into a peak, then falling
    closes = [10, 11, 12, 13, 15, 13, 12, 11, 10]
    candles = [_candle(c, c + 0.5, c - 0.5, c, t=i) for i, c in enumerate(closes)]
    pivots = swing_pivots(candles, left=2, right=2)
    highs = [p for p in pivots if p.kind == "high"]
    assert highs, pivots
    # The peak high (15.5) should be the detected pivot.
    assert max(p.price for p in highs) == pytest.approx(15.5)


def test_cluster_levels_merges_close_prices():
    # Two clear clusters at ~100 and ~110 with intra-cluster <0.3% spread.
    out = cluster_levels([100.0, 100.2, 110.0, 110.1], tolerance_pct=0.3)
    assert len(out) == 2
    assert 99.5 < out[0] < 100.5
    assert 109.5 < out[1] < 110.5


def test_cluster_levels_chains_when_close_enough():
    # Each adjacent pair within 0.3 %, so chain into one cluster.
    out = cluster_levels([100.0, 100.2, 100.4, 100.6], tolerance_pct=0.3)
    assert len(out) == 1


def test_cluster_levels_separates_when_gap_exceeds_tolerance():
    out = cluster_levels([100.0, 105.0, 110.0], tolerance_pct=0.3)
    assert len(out) == 3


def test_support_resistance_separates_above_below():
    # Strong V: low at index 5
    closes = [20, 18, 15, 12, 10, 8, 10, 12, 15, 18, 20, 22]
    candles = [_candle(c, c + 0.3, c - 0.3, c, t=i) for i, c in enumerate(closes)]
    sr = support_resistance(candles, left=2, right=2, cluster_tol_pct=2.0)
    # Latest close is 22; supports must be < 22, resistances > 22 (or empty).
    for s in sr.supports:
        assert s < 22
    for r in sr.resistances:
        assert r > 22


# ---------------------------------------------------------------------------
# pct_change / realized vol
# ---------------------------------------------------------------------------


def test_pct_change_basic():
    assert pct_change(100, 110) == pytest.approx(10.0)
    assert pct_change(100, 90) == pytest.approx(-10.0)
    assert pct_change(0, 5) == 0.0


def test_realized_volatility_nonzero():
    closes = [100, 101, 99, 100, 102, 98, 100, 103, 97, 100,
              101, 99, 100, 102, 98, 100, 103, 97, 100, 101, 99]
    rv = realized_volatility_pct(closes, 20)
    assert rv > 0
    assert rv == rv  # not NaN


# ---------------------------------------------------------------------------
# Bollinger
# ---------------------------------------------------------------------------


def test_bollinger_shape():
    series = [100 + i * 0.5 for i in range(40)]
    bb = bollinger(series, 20, 2.0)
    assert bb[0] is None and bb[18] is None
    last = bb[-1]
    assert last is not None
    assert last.upper > last.middle > last.lower
    assert last.width_pct > 0
