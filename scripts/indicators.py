"""Pure-Python technical indicators.

No external TA libraries — keeps the agency dependency-free for paper mode and
makes every formula auditable. Every function:

  - takes a sequence of `Candle` (or for some, plain price floats),
  - returns the indicator value(s) using ``Decimal`` where price-precision
    matters and ``float`` where speed matters more than precision (e.g. RSI),
  - never mutates the input.

These are the building blocks the Token Research Agent and Strategy Agent use.
Everything is intentionally readable — performance can be optimized later if a
profiling pass shows it matters; in practice we work on at most a few hundred
candles per indicator call.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median
from typing import Sequence

from .market_data import Candle


# ----------------------------------------------------------------------------
# Moving averages
# ----------------------------------------------------------------------------


def ema(values: Sequence[Decimal | float], period: int) -> list[float]:
    """Exponential moving average. First (period-1) entries are NaN-filled with None.

    Returns a list of the same length as input — the agent can align by index.
    """
    if period <= 0:
        raise ValueError("period must be > 0")
    out: list[float] = []
    if len(values) == 0:
        return out
    k = 2 / (period + 1)
    seeded = False
    prev = 0.0
    for i, v in enumerate(values):
        f = float(v)
        if not seeded:
            if i < period - 1:
                out.append(float("nan"))
                continue
            # Seed with simple-MA over the first `period` values.
            seed = sum(float(x) for x in values[: i + 1]) / period
            out.append(seed)
            prev = seed
            seeded = True
        else:
            cur = f * k + prev * (1 - k)
            out.append(cur)
            prev = cur
    return out


def sma(values: Sequence[Decimal | float], period: int) -> list[float]:
    if period <= 0:
        raise ValueError("period must be > 0")
    out: list[float] = []
    rolling = 0.0
    buf: list[float] = []
    for v in values:
        f = float(v)
        buf.append(f)
        rolling += f
        if len(buf) > period:
            rolling -= buf.pop(0)
        if len(buf) < period:
            out.append(float("nan"))
        else:
            out.append(rolling / period)
    return out


# ----------------------------------------------------------------------------
# ATR / volatility
# ----------------------------------------------------------------------------


def true_range(candles: Sequence[Candle]) -> list[float]:
    out: list[float] = [0.0]
    for i in range(1, len(candles)):
        c = candles[i]
        prev_close = float(candles[i - 1].close)
        h = float(c.high)
        l = float(c.low)
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        out.append(tr)
    return out


def atr(candles: Sequence[Candle], period: int = 14) -> list[float]:
    """Wilder-style ATR (RMA of TR). NaN until ``period`` values seen."""
    if period <= 0:
        raise ValueError("period must be > 0")
    tr = true_range(candles)
    out: list[float] = []
    avg = 0.0
    for i, t in enumerate(tr):
        if i < period:
            out.append(float("nan"))
            if i == period - 1:
                avg = sum(tr[1 : period + 1]) / period if len(tr) >= period + 1 else 0.0
            continue
        # Wilder smoothing
        avg = (avg * (period - 1) + t) / period
        out.append(avg)
    return out


def latest_atr_pct(candles: Sequence[Candle], period: int = 14) -> float:
    """Latest ATR as a percentage of the latest close. Returns NaN if not enough data."""
    if len(candles) < period + 1:
        return float("nan")
    a = atr(candles, period)
    last = a[-1]
    close = float(candles[-1].close)
    if close == 0 or last != last:  # NaN check
        return float("nan")
    return last / close * 100.0


# ----------------------------------------------------------------------------
# RSI
# ----------------------------------------------------------------------------


def rsi(values: Sequence[Decimal | float], period: int = 14) -> list[float]:
    """Wilder RSI. Returns 50.0 fill for the first ``period`` values where it
    is mathematically undefined — callers should slice off the warmup window.
    """
    if period <= 0:
        raise ValueError("period must be > 0")
    if len(values) <= period:
        return [50.0] * len(values)

    gains: list[float] = [0.0]
    losses: list[float] = [0.0]
    for i in range(1, len(values)):
        change = float(values[i]) - float(values[i - 1])
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    out: list[float] = [50.0] * period
    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period
    rs = (avg_gain / avg_loss) if avg_loss > 0 else float("inf")
    out.append(100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + rs))

    for i in range(period + 1, len(values)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            out.append(100.0)
        else:
            rs = avg_gain / avg_loss
            out.append(100.0 - 100.0 / (1.0 + rs))
    return out


# ----------------------------------------------------------------------------
# Bollinger Bands
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class BollingerBand:
    middle: float
    upper: float
    lower: float
    width_pct: float    # (upper - lower) / middle * 100


def bollinger(values: Sequence[Decimal | float], period: int = 20, k: float = 2.0) -> list[BollingerBand | None]:
    out: list[BollingerBand | None] = []
    floats = [float(v) for v in values]
    for i in range(len(floats)):
        if i < period - 1:
            out.append(None)
            continue
        window = floats[i - period + 1 : i + 1]
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        std = var ** 0.5
        upper = mean + k * std
        lower = mean - k * std
        width_pct = (upper - lower) / mean * 100.0 if mean else 0.0
        out.append(BollingerBand(middle=mean, upper=upper, lower=lower, width_pct=width_pct))
    return out


# ----------------------------------------------------------------------------
# VWAP
# ----------------------------------------------------------------------------


def vwap(candles: Sequence[Candle]) -> list[float]:
    """Cumulative VWAP over the supplied candles. For session-VWAP, slice the
    candles to the session before calling.
    """
    pv = 0.0
    v = 0.0
    out: list[float] = []
    for c in candles:
        typical = (float(c.high) + float(c.low) + float(c.close)) / 3.0
        pv += typical * float(c.volume)
        v += float(c.volume)
        out.append(pv / v if v > 0 else float("nan"))
    return out


# ----------------------------------------------------------------------------
# Swing highs/lows + support/resistance
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Pivot:
    index: int
    price: float
    kind: str  # 'high' | 'low'


def swing_pivots(candles: Sequence[Candle], left: int = 3, right: int = 3) -> list[Pivot]:
    """Classic fractal pivots: a high (low) is a swing point if it is greater
    (less) than the ``left`` candles before AND ``right`` candles after.

    We compare body+wick highs/lows against the same on the neighbours — the
    Token Research Agent uses these to define support/resistance.
    """
    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")
    out: list[Pivot] = []
    for i in range(left, len(candles) - right):
        c = candles[i]
        h = float(c.high)
        l = float(c.low)
        is_high = all(h >= float(candles[j].high) for j in range(i - left, i + right + 1) if j != i) and \
                  any(h > float(candles[j].high) for j in range(i - left, i + right + 1) if j != i)
        is_low = all(l <= float(candles[j].low) for j in range(i - left, i + right + 1) if j != i) and \
                 any(l < float(candles[j].low) for j in range(i - left, i + right + 1) if j != i)
        if is_high:
            out.append(Pivot(index=i, price=h, kind="high"))
        if is_low:
            out.append(Pivot(index=i, price=l, kind="low"))
    return out


def cluster_levels(prices: Sequence[float], tolerance_pct: float = 0.3) -> list[float]:
    """Cluster nearby prices into single S/R levels.

    Two prices belong in the same cluster if they're within ``tolerance_pct``
    percent of each other. Returns the median price of each cluster, sorted.
    """
    if not prices:
        return []
    sorted_p = sorted(prices)
    clusters: list[list[float]] = [[sorted_p[0]]]
    for p in sorted_p[1:]:
        ref = clusters[-1][-1]
        if ref > 0 and abs(p - ref) / ref * 100.0 <= tolerance_pct:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    return sorted(median(c) for c in clusters)


@dataclass(frozen=True)
class SRLevels:
    supports: tuple[float, ...]      # below the latest close, sorted descending
    resistances: tuple[float, ...]   # above the latest close, sorted ascending


def support_resistance(
    candles: Sequence[Candle],
    *,
    left: int = 3,
    right: int = 3,
    cluster_tol_pct: float = 0.3,
    max_levels_per_side: int = 4,
) -> SRLevels:
    pivots = swing_pivots(candles, left=left, right=right)
    if not pivots:
        return SRLevels(supports=(), resistances=())
    last_close = float(candles[-1].close)
    levels = cluster_levels([p.price for p in pivots], tolerance_pct=cluster_tol_pct)
    supports = sorted([l for l in levels if l < last_close], reverse=True)[:max_levels_per_side]
    resistances = sorted([l for l in levels if l > last_close])[:max_levels_per_side]
    return SRLevels(supports=tuple(supports), resistances=tuple(resistances))


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def pct_change(a: float, b: float) -> float:
    if a == 0:
        return 0.0
    return (b - a) / a * 100.0


def realized_volatility_pct(closes: Sequence[Decimal | float], lookback: int = 20) -> float:
    """Standard deviation of log returns × sqrt(lookback) × 100, expressed as %."""
    if len(closes) < lookback + 1:
        return float("nan")
    import math
    rets = []
    for i in range(len(closes) - lookback, len(closes)):
        prev = float(closes[i - 1])
        cur = float(closes[i])
        if prev > 0 and cur > 0:
            rets.append(math.log(cur / prev))
    if not rets:
        return float("nan")
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return (var ** 0.5) * (lookback ** 0.5) * 100.0


__all__ = [
    "ema", "sma",
    "true_range", "atr", "latest_atr_pct",
    "rsi",
    "BollingerBand", "bollinger",
    "vwap",
    "Pivot", "swing_pivots", "cluster_levels", "SRLevels", "support_resistance",
    "pct_change", "realized_volatility_pct",
]
