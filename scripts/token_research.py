"""Token Research — deep multi-timeframe analysis on a single Binance USDT-M
perpetual. Output is the ``TokenResearchReport`` consumed by the Strategy
Agent.

Per call we hit:
  - klines 4h × 200          (weight 2)   — macro trend
  - klines 1h × 200          (weight 2)   — primary trend / S-R levels
  - klines 15m × 200         (weight 2)   — entry timeframe
  - klines 5m × 100          (weight 1)   — micro confirmation
  - depth limit=50           (weight 2)   — spread + L20 liquidity
  - premiumIndex (symbol)    (weight 1)   — funding state
  - openInterest (symbol)    (weight 1)   — current OI

Total weight per researched symbol ≈ 11. With a per-cycle budget of 2400
weight/min that's ~200 deep researches per minute — far more than we'll ever
need; the screener narrows to ≤5 candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .indicators import (
    SRLevels,
    atr,
    ema,
    latest_atr_pct,
    pct_change,
    realized_volatility_pct,
    rsi,
    support_resistance,
    vwap,
)
from .market_data import (
    Candle,
    MarketData,
    MarkPriceSnapshot,
    OrderBook,
    Ticker24h,
)
from .symbol_filters import SymbolSpec


# ----------------------------------------------------------------------------
# Report dataclasses
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeframeSnapshot:
    """Per-timeframe summary the Strategy Agent uses."""

    interval: str
    candles_examined: int
    last_close: Decimal
    ema_fast: float           # EMA-9 / EMA-21 / EMA-50 stacked depending on TF
    ema_slow: float
    ema_trend: str            # 'up' | 'down' | 'flat'
    rsi_14: float
    atr_pct: float
    realized_vol_pct: float
    sr: SRLevels
    pct_from_nearest_resistance: float | None
    pct_from_nearest_support: float | None
    last_three_close_changes_pct: tuple[float, float, float]
    avg_volume_quote: float        # quote-asset volume avg over examined window
    last_volume_quote: float
    volume_ratio: float            # last / avg


@dataclass(frozen=True)
class StructureFlags:
    """Coarse structural classifications used by the Strategy Agent."""

    is_in_uptrend_1h: bool
    is_in_downtrend_1h: bool
    is_overextended_long: bool       # multi-TF RSI >70, far above EMA stack
    is_overextended_short: bool
    has_recent_pump: bool            # last 6×1h closed +N% vs 6h ago
    has_recent_dump: bool
    failed_breakout_long: bool       # broke 1h resistance, closed back inside
    failed_breakout_short: bool
    pct_from_24h_high: float
    pct_from_24h_low: float


@dataclass(frozen=True)
class LiquidityProfile:
    spread_bps: float | None
    bid_depth_within_0_5pct_usdt: float
    ask_depth_within_0_5pct_usdt: float
    bid_depth_within_2pct_usdt: float
    ask_depth_within_2pct_usdt: float
    is_liquid_for_small_position: bool   # rough: ≥10× our typical 1-2 USDT margin × 5x lev


@dataclass(frozen=True)
class TokenResearchReport:
    symbol: str
    is_decimal_priced: bool
    last_price: Decimal
    mark_price: Decimal
    funding_rate_8h: Decimal
    next_funding_in_minutes: int
    open_interest_base: Decimal
    open_interest_quote_usdt: Decimal       # OI × markPrice
    ticker_24h: dict[str, Any]              # raw-friendly snapshot
    timeframes: dict[str, TimeframeSnapshot]
    structure: StructureFlags
    liquidity: LiquidityProfile
    no_trade_reasons: tuple[str, ...]       # reasons the No-Trade Engine should consider
    spec: SymbolSpec

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "is_decimal_priced": self.is_decimal_priced,
            "last_price": str(self.last_price),
            "mark_price": str(self.mark_price),
            "funding_rate_8h": str(self.funding_rate_8h),
            "next_funding_in_minutes": self.next_funding_in_minutes,
            "open_interest_base": str(self.open_interest_base),
            "open_interest_quote_usdt": str(self.open_interest_quote_usdt),
            "ticker_24h": self.ticker_24h,
            "timeframes": {
                interval: {
                    "candles_examined": tf.candles_examined,
                    "last_close": str(tf.last_close),
                    "ema_fast": tf.ema_fast,
                    "ema_slow": tf.ema_slow,
                    "ema_trend": tf.ema_trend,
                    "rsi_14": tf.rsi_14,
                    "atr_pct": tf.atr_pct,
                    "realized_vol_pct": tf.realized_vol_pct,
                    "supports": [str(x) for x in tf.sr.supports],
                    "resistances": [str(x) for x in tf.sr.resistances],
                    "pct_from_nearest_resistance": tf.pct_from_nearest_resistance,
                    "pct_from_nearest_support": tf.pct_from_nearest_support,
                    "last_three_close_changes_pct": list(tf.last_three_close_changes_pct),
                    "avg_volume_quote": tf.avg_volume_quote,
                    "last_volume_quote": tf.last_volume_quote,
                    "volume_ratio": tf.volume_ratio,
                }
                for interval, tf in self.timeframes.items()
            },
            "structure": {
                "is_in_uptrend_1h": self.structure.is_in_uptrend_1h,
                "is_in_downtrend_1h": self.structure.is_in_downtrend_1h,
                "is_overextended_long": self.structure.is_overextended_long,
                "is_overextended_short": self.structure.is_overextended_short,
                "has_recent_pump": self.structure.has_recent_pump,
                "has_recent_dump": self.structure.has_recent_dump,
                "failed_breakout_long": self.structure.failed_breakout_long,
                "failed_breakout_short": self.structure.failed_breakout_short,
                "pct_from_24h_high": self.structure.pct_from_24h_high,
                "pct_from_24h_low": self.structure.pct_from_24h_low,
            },
            "liquidity": {
                "spread_bps": self.liquidity.spread_bps,
                "bid_depth_within_0_5pct_usdt": self.liquidity.bid_depth_within_0_5pct_usdt,
                "ask_depth_within_0_5pct_usdt": self.liquidity.ask_depth_within_0_5pct_usdt,
                "bid_depth_within_2pct_usdt": self.liquidity.bid_depth_within_2pct_usdt,
                "ask_depth_within_2pct_usdt": self.liquidity.ask_depth_within_2pct_usdt,
                "is_liquid_for_small_position": self.liquidity.is_liquid_for_small_position,
            },
            "no_trade_reasons": list(self.no_trade_reasons),
        }


# ----------------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------------

# (interval, candles, fast_ema, slow_ema)
_TIMEFRAME_PLAN: tuple[tuple[str, int, int, int], ...] = (
    ("4h", 200, 21, 50),
    ("1h", 200, 9, 21),
    ("15m", 200, 9, 21),
    ("5m", 100, 9, 21),
)


def research_token(
    market: MarketData,
    spec: SymbolSpec,
    ticker_24h: Ticker24h | None = None,
) -> TokenResearchReport:
    """Build a full research report for one symbol.

    Pass the ``Ticker24h`` from the screener if you already have it — saves a
    weight-1 call per token.
    """
    if ticker_24h is None:
        ticker_24h = market.get_ticker_24h(spec.symbol)

    mark = market.get_mark_price(spec.symbol)
    oi = market.get_open_interest(spec.symbol)
    book = market.get_order_book(spec.symbol, limit=50)

    timeframes: dict[str, TimeframeSnapshot] = {}
    for interval, n, fast, slow in _TIMEFRAME_PLAN:
        candles = market.get_klines(spec.symbol, interval, limit=n)
        if not candles:
            continue
        timeframes[interval] = _summarize_timeframe(interval, candles, fast, slow)

    structure = _classify_structure(timeframes, ticker_24h)
    liquidity = _liquidity_profile(book)
    no_trade_reasons = _no_trade_reasons(ticker_24h, mark, liquidity, structure, timeframes)

    return TokenResearchReport(
        symbol=spec.symbol,
        is_decimal_priced=spec.is_decimal_priced,
        last_price=ticker_24h.last_price,
        mark_price=mark.mark_price,
        funding_rate_8h=mark.last_funding_rate,
        next_funding_in_minutes=_minutes_until(mark.next_funding_time_ms),
        open_interest_base=oi.open_interest_base,
        open_interest_quote_usdt=oi.open_interest_base * mark.mark_price,
        ticker_24h={
            "open": str(ticker_24h.open_price),
            "high": str(ticker_24h.high_price),
            "low": str(ticker_24h.low_price),
            "last": str(ticker_24h.last_price),
            "change_pct": str(ticker_24h.price_change_pct),
            "quote_volume_usdt": str(ticker_24h.quote_volume),
            "trades": ticker_24h.trades,
        },
        timeframes=timeframes,
        structure=structure,
        liquidity=liquidity,
        no_trade_reasons=no_trade_reasons,
        spec=spec,
    )


# ----------------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------------


def _summarize_timeframe(
    interval: str, candles: list[Candle], fast: int, slow: int
) -> TimeframeSnapshot:
    closes = [c.close for c in candles]
    ema_fast = _last_finite(ema(closes, fast))
    ema_slow = _last_finite(ema(closes, slow))
    last_close = float(closes[-1])

    if ema_fast is None or ema_slow is None:
        trend = "flat"
    else:
        gap = (ema_fast - ema_slow) / max(abs(ema_slow), 1e-12) * 100.0
        if gap > 0.15 and last_close > ema_fast:
            trend = "up"
        elif gap < -0.15 and last_close < ema_fast:
            trend = "down"
        else:
            trend = "flat"

    rsi_vals = rsi(closes, 14)
    rsi_last = rsi_vals[-1] if rsi_vals else 50.0

    atr_pct = latest_atr_pct(candles, 14)
    rv_pct = realized_volatility_pct(closes, 20)

    sr = support_resistance(candles, left=3, right=3, cluster_tol_pct=0.3, max_levels_per_side=4)
    pct_from_resistance: float | None = None
    if sr.resistances:
        pct_from_resistance = pct_change(last_close, float(sr.resistances[0]))
    pct_from_support: float | None = None
    if sr.supports:
        pct_from_support = pct_change(last_close, float(sr.supports[0]))

    last_three: list[float] = []
    for i in range(max(len(candles) - 3, 1), len(candles)):
        if i == 0:
            continue
        last_three.append(pct_change(float(candles[i - 1].close), float(candles[i].close)))
    while len(last_three) < 3:
        last_three.insert(0, 0.0)
    last_three_t = (last_three[0], last_three[1], last_three[2])

    quote_vols = [float(c.quote_volume) for c in candles]
    avg_qv = sum(quote_vols) / len(quote_vols) if quote_vols else 0.0
    last_qv = quote_vols[-1] if quote_vols else 0.0
    vol_ratio = last_qv / avg_qv if avg_qv > 0 else 0.0

    return TimeframeSnapshot(
        interval=interval,
        candles_examined=len(candles),
        last_close=closes[-1],
        ema_fast=ema_fast if ema_fast is not None else float("nan"),
        ema_slow=ema_slow if ema_slow is not None else float("nan"),
        ema_trend=trend,
        rsi_14=rsi_last,
        atr_pct=atr_pct,
        realized_vol_pct=rv_pct,
        sr=sr,
        pct_from_nearest_resistance=pct_from_resistance,
        pct_from_nearest_support=pct_from_support,
        last_three_close_changes_pct=last_three_t,
        avg_volume_quote=avg_qv,
        last_volume_quote=last_qv,
        volume_ratio=vol_ratio,
    )


def _classify_structure(
    timeframes: dict[str, TimeframeSnapshot], ticker: Ticker24h
) -> StructureFlags:
    one_h = timeframes.get("1h")
    fifteen = timeframes.get("15m")

    in_up = bool(one_h and one_h.ema_trend == "up")
    in_dn = bool(one_h and one_h.ema_trend == "down")

    overext_long = bool(
        one_h and fifteen
        and one_h.rsi_14 >= 70 and fifteen.rsi_14 >= 70
    )
    overext_short = bool(
        one_h and fifteen
        and one_h.rsi_14 <= 30 and fifteen.rsi_14 <= 30
    )

    # A "recent pump" = sum of last 6×1h closes shows +5% or more
    pump = False
    dump = False
    if one_h and one_h.candles_examined >= 7:
        closes = [one_h.last_close]
        # we already collapsed the timeframe; reconstruct using last_three for a coarse signal
        # but better: take the last_three_close_changes_pct sum as a proxy
        coarse = sum(one_h.last_three_close_changes_pct)
        pump = coarse > 4.0
        dump = coarse < -4.0

    failed_long = False
    failed_short = False
    if one_h and one_h.sr.resistances and len(one_h.sr.resistances) > 0:
        r0 = float(one_h.sr.resistances[0])
        last = float(one_h.last_close)
        # if very close above (i.e., we tagged it within 0.3%), it's still ambiguous;
        # failed-breakout is when we exceeded it on a recent candle but closed back below.
        # Use last_three changes: if any of them was strongly +, but we now sit below r0:
        if last < r0 and any(ch > 1.0 for ch in one_h.last_three_close_changes_pct) and pump:
            failed_long = True
    if one_h and one_h.sr.supports and len(one_h.sr.supports) > 0:
        s0 = float(one_h.sr.supports[0])
        last = float(one_h.last_close)
        if last > s0 and any(ch < -1.0 for ch in one_h.last_three_close_changes_pct) and dump:
            failed_short = True

    pct_from_24h_high = pct_change(float(ticker.high_price), float(ticker.last_price))
    pct_from_24h_low = pct_change(float(ticker.low_price), float(ticker.last_price))

    return StructureFlags(
        is_in_uptrend_1h=in_up,
        is_in_downtrend_1h=in_dn,
        is_overextended_long=overext_long,
        is_overextended_short=overext_short,
        has_recent_pump=pump,
        has_recent_dump=dump,
        failed_breakout_long=failed_long,
        failed_breakout_short=failed_short,
        pct_from_24h_high=pct_from_24h_high,
        pct_from_24h_low=pct_from_24h_low,
    )


def _liquidity_profile(book: OrderBook) -> LiquidityProfile:
    spread = book.spread_bps
    bid_05 = float(book.depth_quote_within_pct(Decimal("0.5"), "bid"))
    ask_05 = float(book.depth_quote_within_pct(Decimal("0.5"), "ask"))
    bid_2 = float(book.depth_quote_within_pct(Decimal("2"), "bid"))
    ask_2 = float(book.depth_quote_within_pct(Decimal("2"), "ask"))

    # 1-2 USDT margin × 5x leverage = ~10 USDT notional.
    # Require at least ~100 USDT depth within 0.5% on both sides — 10x cover.
    is_liquid = (bid_05 >= 100 and ask_05 >= 100)

    return LiquidityProfile(
        spread_bps=float(spread) if spread is not None else None,
        bid_depth_within_0_5pct_usdt=bid_05,
        ask_depth_within_0_5pct_usdt=ask_05,
        bid_depth_within_2pct_usdt=bid_2,
        ask_depth_within_2pct_usdt=ask_2,
        is_liquid_for_small_position=is_liquid,
    )


def _no_trade_reasons(
    ticker: Ticker24h,
    mark: MarkPriceSnapshot,
    liq: LiquidityProfile,
    structure: StructureFlags,
    timeframes: dict[str, TimeframeSnapshot],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if liq.spread_bps is not None and liq.spread_bps > 20:
        reasons.append(f"spread {liq.spread_bps:.1f} bps > 20 bps")
    if not liq.is_liquid_for_small_position:
        reasons.append(
            f"thin order book (within 0.5%: bid {liq.bid_depth_within_0_5pct_usdt:.0f} USDT, "
            f"ask {liq.ask_depth_within_0_5pct_usdt:.0f} USDT)"
        )
    if abs(float(mark.last_funding_rate)) > 0.005:
        reasons.append(f"extreme funding {float(mark.last_funding_rate):.4f} per 8h")
    if structure.is_overextended_long and structure.has_recent_pump:
        reasons.append("overextended after pump — long entries dangerous, short setups need confirmation")
    if structure.is_overextended_short and structure.has_recent_dump:
        reasons.append("overextended after dump — short entries dangerous, long reversal needs confirmation")
    one_h = timeframes.get("1h")
    if one_h and one_h.atr_pct != one_h.atr_pct:   # NaN check
        reasons.append("1h ATR unavailable (insufficient candles)")
    return tuple(reasons)


def _minutes_until(target_ms: int) -> int:
    if target_ms <= 0:
        return -1
    import time
    now = int(time.time() * 1000)
    return max(0, (target_ms - now) // 60_000)


def _last_finite(values: list[float]) -> float | None:
    for v in reversed(values):
        if v == v:           # not NaN
            return v
    return None


__all__ = [
    "TimeframeSnapshot",
    "StructureFlags",
    "LiquidityProfile",
    "TokenResearchReport",
    "research_token",
]
