"""Strategy scoring — convert a TokenResearchReport into a ranked list of
candidate setups and pick the best one (or no_trade).

Each strategy is a small pure function that:
  - reads the research report,
  - returns a `StrategyScore` with confidence in [0, 1] plus an entry zone,
    invalidation, take-profit ladder, expected hold time, regime fit, and
    the reasons it likes/dislikes the setup.

Strategies (8):
  1. long_breakout            — close near 1h resistance, bullish structure
  2. short_breakdown          — close near 1h support, bearish structure
  3. pullback_long            — uptrend, RSI cooled, near EMA / support
  4. pullback_short           — downtrend, RSI bounced, near EMA / resistance
  5. momentum_continuation    — strong directional move with volume confirmation
  6. failed_breakout_short    — pump tagged resistance and got rejected
  7. short_after_pump         — overextended pump cooling, bear divergence
  8. reversal_scalp           — extreme RSI + 24h-high/low rejection wick
  9. range_trade              — sideways, between support/resistance, low ATR

Anything below `MIN_CONFIDENCE` becomes ``no_trade``. The Trade Decision Agent
takes the ranked output and either creates a TradeProposal for the top setup
or rejects all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from .token_research import TokenResearchReport, TimeframeSnapshot


# ----------------------------------------------------------------------------
# Tunables
# ----------------------------------------------------------------------------

MIN_CONFIDENCE = 0.6


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyScore:
    strategy: str
    side: str                       # "LONG" | "SHORT" | "NONE"
    confidence: float               # 0..1
    entry_zone: tuple[Decimal, Decimal] | None
    invalidation: Decimal | None    # stop-loss reference price
    take_profit_targets: tuple[Decimal, ...]
    expected_hold_time: str         # "scalp 5-30m" | "intraday" | "swing 1-3 days"
    regime_fit: str                 # "bullish" | "bearish" | "any" | "volatile"
    pros: tuple[str, ...]
    cons: tuple[str, ...]

    def to_jsonable(self) -> dict:
        return {
            "strategy": self.strategy,
            "side": self.side,
            "confidence": round(self.confidence, 3),
            "entry_zone": [str(e) for e in self.entry_zone] if self.entry_zone else None,
            "invalidation": str(self.invalidation) if self.invalidation is not None else None,
            "take_profit_targets": [str(t) for t in self.take_profit_targets],
            "expected_hold_time": self.expected_hold_time,
            "regime_fit": self.regime_fit,
            "pros": list(self.pros),
            "cons": list(self.cons),
        }


@dataclass(frozen=True)
class StrategyRanking:
    symbol: str
    scores: tuple[StrategyScore, ...]    # sorted desc by confidence
    best: StrategyScore | None           # highest confidence ≥ MIN_CONFIDENCE, else None

    def to_jsonable(self) -> dict:
        return {
            "symbol": self.symbol,
            "best_strategy": self.best.to_jsonable() if self.best else None,
            "all_scores": [s.to_jsonable() for s in self.scores],
        }


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------


def rank_strategies(report: TokenResearchReport) -> StrategyRanking:
    scorers: tuple[Callable[[TokenResearchReport], StrategyScore], ...] = (
        _long_breakout,
        _short_breakdown,
        _pullback_long,
        _pullback_short,
        _momentum_continuation,
        _failed_breakout_short,
        _short_after_pump,
        _reversal_scalp,
        _range_trade,
    )
    scores = sorted(
        (s(report) for s in scorers),
        key=lambda s: s.confidence,
        reverse=True,
    )
    best = next((s for s in scores if s.confidence >= MIN_CONFIDENCE and s.side != "NONE"), None)
    # If liquidity is poor or there's a hard no-trade reason, force best=None.
    if report.no_trade_reasons:
        # Reasons from research are *advisory*, not absolute — but spread/funding
        # blockers should kill all directional plays here.
        if any("spread" in r or "thin order book" in r or "extreme funding" in r for r in report.no_trade_reasons):
            best = None
    return StrategyRanking(symbol=report.symbol, scores=tuple(scores), best=best)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _atr_distance(report: TokenResearchReport, interval: str = "1h", multiple: float = 1.5) -> Decimal:
    tf = report.timeframes.get(interval)
    if tf is None or tf.atr_pct != tf.atr_pct:   # NaN check
        # fall back to 1% of price
        return report.last_price * Decimal("0.01") * Decimal(str(multiple))
    return report.last_price * Decimal(str(tf.atr_pct / 100.0)) * Decimal(str(multiple))


def _rr_targets(side: str, entry: Decimal, stop: Decimal, multiples: tuple[float, ...]) -> tuple[Decimal, ...]:
    risk = abs(entry - stop)
    if risk == 0:
        return tuple()
    targets: list[Decimal] = []
    for m in multiples:
        offset = risk * Decimal(str(m))
        targets.append(entry + offset if side == "LONG" else entry - offset)
    return tuple(targets)


def _safe_tf(report: TokenResearchReport, interval: str) -> TimeframeSnapshot | None:
    return report.timeframes.get(interval)


def _none_score(strategy: str, side: str, regime: str, cons: list[str]) -> StrategyScore:
    return StrategyScore(
        strategy=strategy,
        side=side,
        confidence=0.0,
        entry_zone=None,
        invalidation=None,
        take_profit_targets=tuple(),
        expected_hold_time="-",
        regime_fit=regime,
        pros=tuple(),
        cons=tuple(cons),
    )


# ----------------------------------------------------------------------------
# Individual strategies
# ----------------------------------------------------------------------------


def _long_breakout(r: TokenResearchReport) -> StrategyScore:
    one_h = _safe_tf(r, "1h")
    fifteen = _safe_tf(r, "15m")
    if not (one_h and fifteen) or not one_h.sr.resistances:
        return _none_score("long_breakout", "LONG", "bullish", ["missing 1h resistance levels"])

    pros: list[str] = []
    cons: list[str] = []
    conf = 0.0

    last = r.last_price
    r0 = Decimal(str(one_h.sr.resistances[0]))
    pct_to_r = (r0 - last) / last * Decimal("100")

    # Within 0.4% below resistance with bullish stack — primed for break.
    if Decimal("0") <= pct_to_r <= Decimal("0.5") and one_h.ema_trend == "up":
        conf += 0.45
        pros.append(f"price within {pct_to_r:.2f}% of 1h resistance, 1h trend up")
    elif pct_to_r > Decimal("1.5"):
        cons.append(f"too far ({pct_to_r:.2f}%) from nearest resistance for a breakout")
    elif pct_to_r < Decimal("-0.3"):
        cons.append("already extended past nearest resistance — chase risk")

    if fifteen.ema_trend == "up":
        conf += 0.15
        pros.append("15m EMA stack confirms uptrend")
    if 50 <= fifteen.rsi_14 <= 68:
        conf += 0.10
        pros.append(f"15m RSI {fifteen.rsi_14:.0f} — strong but not overbought")
    elif fifteen.rsi_14 > 75:
        conf -= 0.15
        cons.append(f"15m RSI {fifteen.rsi_14:.0f} overbought — buying late")

    if fifteen.volume_ratio >= 1.3:
        conf += 0.15
        pros.append(f"15m volume {fifteen.volume_ratio:.2f}× avg")
    elif fifteen.volume_ratio < 0.7:
        cons.append("weak 15m volume — breakout unlikely without participation")

    if r.structure.is_overextended_long:
        conf -= 0.20
        cons.append("multi-TF RSI shows overextension")

    conf = max(0.0, min(conf, 0.95))

    if conf < 0.4:
        return _none_score("long_breakout", "LONG", "bullish", cons or ["composite confidence too low"])

    entry_low = r0 * Decimal("0.999")
    entry_high = r0 * Decimal("1.002")
    stop = last - _atr_distance(r, "1h", 1.2)
    tps = _rr_targets("LONG", (entry_low + entry_high) / 2, stop, (1.5, 2.5, 4.0))
    return StrategyScore(
        strategy="long_breakout",
        side="LONG",
        confidence=conf,
        entry_zone=(entry_low, entry_high),
        invalidation=stop,
        take_profit_targets=tps,
        expected_hold_time="intraday",
        regime_fit="bullish",
        pros=tuple(pros),
        cons=tuple(cons),
    )


def _short_breakdown(r: TokenResearchReport) -> StrategyScore:
    one_h = _safe_tf(r, "1h")
    fifteen = _safe_tf(r, "15m")
    if not (one_h and fifteen) or not one_h.sr.supports:
        return _none_score("short_breakdown", "SHORT", "bearish", ["missing 1h support levels"])

    pros: list[str] = []
    cons: list[str] = []
    conf = 0.0
    last = r.last_price
    s0 = Decimal(str(one_h.sr.supports[0]))
    pct_to_s = (last - s0) / last * Decimal("100")

    if Decimal("0") <= pct_to_s <= Decimal("0.5") and one_h.ema_trend == "down":
        conf += 0.45
        pros.append(f"price within {pct_to_s:.2f}% of 1h support, 1h trend down")
    elif pct_to_s > Decimal("1.5"):
        cons.append(f"too far ({pct_to_s:.2f}%) above support for breakdown")
    elif pct_to_s < Decimal("-0.3"):
        cons.append("already broken support — chase risk")

    if fifteen.ema_trend == "down":
        conf += 0.15
        pros.append("15m EMA stack confirms downtrend")
    if 32 <= fifteen.rsi_14 <= 50:
        conf += 0.10
        pros.append(f"15m RSI {fifteen.rsi_14:.0f} — weak but not yet oversold")
    elif fifteen.rsi_14 < 25:
        conf -= 0.15
        cons.append(f"15m RSI {fifteen.rsi_14:.0f} oversold — selling late")

    if fifteen.volume_ratio >= 1.3:
        conf += 0.15
        pros.append(f"15m volume {fifteen.volume_ratio:.2f}× avg")

    if r.structure.is_overextended_short:
        conf -= 0.20
        cons.append("multi-TF RSI shows oversold extreme")

    conf = max(0.0, min(conf, 0.95))
    if conf < 0.4:
        return _none_score("short_breakdown", "SHORT", "bearish", cons or ["composite confidence too low"])

    entry_low = s0 * Decimal("0.998")
    entry_high = s0 * Decimal("1.001")
    stop = last + _atr_distance(r, "1h", 1.2)
    tps = _rr_targets("SHORT", (entry_low + entry_high) / 2, stop, (1.5, 2.5, 4.0))
    return StrategyScore(
        strategy="short_breakdown",
        side="SHORT",
        confidence=conf,
        entry_zone=(entry_low, entry_high),
        invalidation=stop,
        take_profit_targets=tps,
        expected_hold_time="intraday",
        regime_fit="bearish",
        pros=tuple(pros),
        cons=tuple(cons),
    )


def _pullback_long(r: TokenResearchReport) -> StrategyScore:
    one_h = _safe_tf(r, "1h")
    fifteen = _safe_tf(r, "15m")
    if not (one_h and fifteen):
        return _none_score("pullback_long", "LONG", "bullish", ["missing timeframes"])
    if one_h.ema_trend != "up":
        return _none_score("pullback_long", "LONG", "bullish", ["1h not in uptrend"])

    pros: list[str] = []
    cons: list[str] = []
    conf = 0.30
    pros.append("1h is in uptrend (EMA stack)")

    if 38 <= fifteen.rsi_14 <= 55:
        conf += 0.20
        pros.append(f"15m RSI cooled to {fifteen.rsi_14:.0f}")
    elif fifteen.rsi_14 < 30:
        conf += 0.10
        pros.append(f"15m RSI {fifteen.rsi_14:.0f} oversold — bounce candidate")
    elif fifteen.rsi_14 > 65:
        cons.append(f"15m RSI {fifteen.rsi_14:.0f} not pulled back enough")

    last = r.last_price
    if one_h.sr.supports:
        s0 = Decimal(str(one_h.sr.supports[0]))
        pct = (last - s0) / last * Decimal("100")
        if Decimal("0") <= pct <= Decimal("1.5"):
            conf += 0.20
            pros.append(f"near 1h support ({pct:.2f}% above)")
        else:
            cons.append(f"not near 1h support ({pct:.2f}%)")

    if r.structure.has_recent_pump:
        conf -= 0.10
        cons.append("recent pump — pullback may extend further")
    if r.structure.is_in_downtrend_1h:
        conf -= 0.20
        cons.append("conflicting 1h downtrend signal")

    conf = max(0.0, min(conf, 0.90))
    if conf < 0.4:
        return _none_score("pullback_long", "LONG", "bullish", cons)

    stop = last - _atr_distance(r, "15m", 1.5)
    entry_low = last * Decimal("0.997")
    entry_high = last * Decimal("1.001")
    tps = _rr_targets("LONG", last, stop, (1.5, 2.5))
    return StrategyScore(
        strategy="pullback_long", side="LONG", confidence=conf,
        entry_zone=(entry_low, entry_high), invalidation=stop,
        take_profit_targets=tps, expected_hold_time="scalp 30m-2h",
        regime_fit="bullish", pros=tuple(pros), cons=tuple(cons),
    )


def _pullback_short(r: TokenResearchReport) -> StrategyScore:
    one_h = _safe_tf(r, "1h")
    fifteen = _safe_tf(r, "15m")
    if not (one_h and fifteen):
        return _none_score("pullback_short", "SHORT", "bearish", ["missing timeframes"])
    if one_h.ema_trend != "down":
        return _none_score("pullback_short", "SHORT", "bearish", ["1h not in downtrend"])

    pros: list[str] = []
    cons: list[str] = []
    conf = 0.30
    pros.append("1h is in downtrend (EMA stack)")

    if 45 <= fifteen.rsi_14 <= 62:
        conf += 0.20
        pros.append(f"15m RSI bounced to {fifteen.rsi_14:.0f}")
    elif fifteen.rsi_14 > 70:
        conf += 0.10
        pros.append(f"15m RSI {fifteen.rsi_14:.0f} overbought — fade candidate")
    elif fifteen.rsi_14 < 35:
        cons.append(f"15m RSI {fifteen.rsi_14:.0f} not bounced enough")

    last = r.last_price
    if one_h.sr.resistances:
        r0 = Decimal(str(one_h.sr.resistances[0]))
        pct = (r0 - last) / last * Decimal("100")
        if Decimal("0") <= pct <= Decimal("1.5"):
            conf += 0.20
            pros.append(f"near 1h resistance ({pct:.2f}% below)")

    if r.structure.has_recent_dump:
        conf -= 0.10
        cons.append("recent dump — bounce may extend higher")

    conf = max(0.0, min(conf, 0.90))
    if conf < 0.4:
        return _none_score("pullback_short", "SHORT", "bearish", cons)

    stop = last + _atr_distance(r, "15m", 1.5)
    entry_low = last * Decimal("0.999")
    entry_high = last * Decimal("1.003")
    tps = _rr_targets("SHORT", last, stop, (1.5, 2.5))
    return StrategyScore(
        strategy="pullback_short", side="SHORT", confidence=conf,
        entry_zone=(entry_low, entry_high), invalidation=stop,
        take_profit_targets=tps, expected_hold_time="scalp 30m-2h",
        regime_fit="bearish", pros=tuple(pros), cons=tuple(cons),
    )


def _momentum_continuation(r: TokenResearchReport) -> StrategyScore:
    one_h = _safe_tf(r, "1h")
    fifteen = _safe_tf(r, "15m")
    if not (one_h and fifteen):
        return _none_score("momentum_continuation", "NONE", "any", ["missing timeframes"])

    side = "NONE"
    conf = 0.0
    pros: list[str] = []
    cons: list[str] = []

    if one_h.ema_trend == "up" and fifteen.ema_trend == "up" and fifteen.volume_ratio >= 1.4:
        side = "LONG"
        conf = 0.45
        pros.append(f"both 1h and 15m up; 15m vol {fifteen.volume_ratio:.2f}× avg")
        if 55 <= fifteen.rsi_14 <= 70:
            conf += 0.15
            pros.append(f"15m RSI {fifteen.rsi_14:.0f} — strong without exhaustion")
    elif one_h.ema_trend == "down" and fifteen.ema_trend == "down" and fifteen.volume_ratio >= 1.4:
        side = "SHORT"
        conf = 0.45
        pros.append(f"both 1h and 15m down; 15m vol {fifteen.volume_ratio:.2f}× avg")
        if 30 <= fifteen.rsi_14 <= 45:
            conf += 0.15
            pros.append(f"15m RSI {fifteen.rsi_14:.0f} — weak without exhaustion")
    else:
        return _none_score(
            "momentum_continuation", "NONE", "any",
            ["mixed trend or insufficient volume"]
        )

    if r.structure.is_overextended_long and side == "LONG":
        conf -= 0.20; cons.append("overextended long")
    if r.structure.is_overextended_short and side == "SHORT":
        conf -= 0.20; cons.append("overextended short")

    conf = max(0.0, min(conf, 0.92))
    if conf < 0.4:
        return _none_score("momentum_continuation", side, "any", cons)

    last = r.last_price
    stop = last - _atr_distance(r, "15m", 1.4) if side == "LONG" else last + _atr_distance(r, "15m", 1.4)
    entry_zone = (last * Decimal("0.998"), last * Decimal("1.002"))
    tps = _rr_targets(side, last, stop, (1.5, 2.5, 4.0))
    return StrategyScore(
        strategy="momentum_continuation", side=side, confidence=conf,
        entry_zone=entry_zone, invalidation=stop,
        take_profit_targets=tps, expected_hold_time="intraday",
        regime_fit="any", pros=tuple(pros), cons=tuple(cons),
    )


def _failed_breakout_short(r: TokenResearchReport) -> StrategyScore:
    if not r.structure.failed_breakout_long:
        return _none_score("failed_breakout_short", "SHORT", "bearish", ["no failed breakout pattern"])
    one_h = _safe_tf(r, "1h")
    fifteen = _safe_tf(r, "15m")
    if not (one_h and fifteen):
        return _none_score("failed_breakout_short", "SHORT", "bearish", ["missing timeframes"])

    pros = ["1h showed failed breakout above resistance"]
    cons: list[str] = []
    conf = 0.45
    if fifteen.ema_trend == "down":
        conf += 0.15; pros.append("15m EMA stack rolling over")
    if fifteen.rsi_14 > 60:
        conf += 0.10; pros.append(f"15m RSI {fifteen.rsi_14:.0f} still elevated — room to fall")

    last = r.last_price
    if one_h.sr.resistances:
        r0 = Decimal(str(one_h.sr.resistances[0]))
        if r0 > last:
            stop = r0 * Decimal("1.003")
        else:
            stop = last + _atr_distance(r, "1h", 1.2)
    else:
        stop = last + _atr_distance(r, "1h", 1.2)

    conf = max(0.0, min(conf, 0.92))
    if conf < 0.4:
        return _none_score("failed_breakout_short", "SHORT", "bearish", cons)
    tps = _rr_targets("SHORT", last, stop, (1.5, 2.5, 3.5))
    return StrategyScore(
        strategy="failed_breakout_short", side="SHORT", confidence=conf,
        entry_zone=(last * Decimal("0.999"), last * Decimal("1.002")), invalidation=stop,
        take_profit_targets=tps, expected_hold_time="intraday",
        regime_fit="bearish", pros=tuple(pros), cons=tuple(cons),
    )


def _short_after_pump(r: TokenResearchReport) -> StrategyScore:
    if not r.structure.has_recent_pump:
        return _none_score("short_after_pump", "SHORT", "bearish", ["no recent pump"])
    fifteen = _safe_tf(r, "15m")
    five = _safe_tf(r, "5m")
    if not (fifteen and five):
        return _none_score("short_after_pump", "SHORT", "bearish", ["missing 15m/5m timeframes"])

    pros = ["recent multi-hour pump detected"]
    cons: list[str] = []
    conf = 0.35

    if fifteen.rsi_14 >= 70:
        conf += 0.20; pros.append(f"15m RSI {fifteen.rsi_14:.0f} overbought")
    if five.rsi_14 < 60 and fifteen.rsi_14 >= 65:
        conf += 0.15; pros.append("bearish RSI divergence (5m cooling vs 15m hot)")
    if r.structure.pct_from_24h_high > -1.0:
        conf += 0.10; pros.append(f"price {r.structure.pct_from_24h_high:.2f}% from 24h high")
    if fifteen.last_three_close_changes_pct[-1] < 0:
        conf += 0.05; pros.append("most recent 15m closed down")

    if not r.liquidity.is_liquid_for_small_position:
        conf -= 0.20; cons.append("thin liquidity")

    last = r.last_price
    stop = last + _atr_distance(r, "15m", 1.6)
    conf = max(0.0, min(conf, 0.92))
    if conf < 0.4:
        return _none_score("short_after_pump", "SHORT", "bearish", cons or ["confidence too low"])
    tps = _rr_targets("SHORT", last, stop, (1.5, 2.5, 4.0))
    return StrategyScore(
        strategy="short_after_pump", side="SHORT", confidence=conf,
        entry_zone=(last * Decimal("0.999"), last * Decimal("1.003")), invalidation=stop,
        take_profit_targets=tps, expected_hold_time="intraday",
        regime_fit="volatile", pros=tuple(pros), cons=tuple(cons),
    )


def _reversal_scalp(r: TokenResearchReport) -> StrategyScore:
    fifteen = _safe_tf(r, "15m")
    five = _safe_tf(r, "5m")
    if not (fifteen and five):
        return _none_score("reversal_scalp", "NONE", "volatile", ["missing 15m/5m timeframes"])

    side = "NONE"
    conf = 0.0
    pros: list[str] = []
    cons: list[str] = []

    if r.structure.pct_from_24h_low > -0.3 and five.rsi_14 < 25:
        side = "LONG"
        conf = 0.40
        pros.append(f"tagged 24h low; 5m RSI {five.rsi_14:.0f}")
        if fifteen.rsi_14 < 35:
            conf += 0.10; pros.append(f"15m RSI {fifteen.rsi_14:.0f} confirms exhaustion")
    elif r.structure.pct_from_24h_high < 0.3 and five.rsi_14 > 75:
        side = "SHORT"
        conf = 0.40
        pros.append(f"tagged 24h high; 5m RSI {five.rsi_14:.0f}")
        if fifteen.rsi_14 > 65:
            conf += 0.10; pros.append(f"15m RSI {fifteen.rsi_14:.0f} confirms exhaustion")
    else:
        return _none_score("reversal_scalp", "NONE", "volatile", ["no clean reversal trigger"])

    last = r.last_price
    stop_atr = _atr_distance(r, "5m", 1.5)
    stop = last - stop_atr if side == "LONG" else last + stop_atr

    # Reversal scalps must clear at least 1.2R after fees — small wallets can't afford many of these.
    conf = max(0.0, min(conf, 0.78))
    if conf < 0.4:
        return _none_score("reversal_scalp", side, "volatile", cons)
    tps = _rr_targets(side, last, stop, (1.0, 2.0))
    return StrategyScore(
        strategy="reversal_scalp", side=side, confidence=conf,
        entry_zone=(last * Decimal("0.999"), last * Decimal("1.001")), invalidation=stop,
        take_profit_targets=tps, expected_hold_time="scalp 5-30m",
        regime_fit="volatile", pros=tuple(pros), cons=tuple(cons),
    )


def _range_trade(r: TokenResearchReport) -> StrategyScore:
    one_h = _safe_tf(r, "1h")
    if not one_h:
        return _none_score("range_trade", "NONE", "any", ["missing 1h timeframe"])
    if one_h.ema_trend != "flat":
        return _none_score("range_trade", "NONE", "any", ["1h not flat"])
    if not (one_h.sr.supports and one_h.sr.resistances):
        return _none_score("range_trade", "NONE", "any", ["no clean range bounds"])

    last = r.last_price
    s0 = Decimal(str(one_h.sr.supports[0]))
    r0 = Decimal(str(one_h.sr.resistances[0]))
    pct_to_s = (last - s0) / last * Decimal("100")
    pct_to_r = (r0 - last) / last * Decimal("100")

    pros: list[str] = ["1h flat with defined range bounds"]
    cons: list[str] = []
    conf = 0.0
    side = "NONE"

    if pct_to_s < pct_to_r and pct_to_s <= Decimal("1"):
        side = "LONG"
        conf = 0.45
        pros.append(f"near range support ({pct_to_s:.2f}% above)")
        stop = s0 * Decimal("0.997")
        tps = (last + (r0 - last) * Decimal("0.7"), r0)
    elif pct_to_r < pct_to_s and pct_to_r <= Decimal("1"):
        side = "SHORT"
        conf = 0.45
        pros.append(f"near range resistance ({pct_to_r:.2f}% below)")
        stop = r0 * Decimal("1.003")
        tps = (last - (last - s0) * Decimal("0.7"), s0)
    else:
        return _none_score("range_trade", "NONE", "any", ["mid-range — no edge"])

    if one_h.atr_pct == one_h.atr_pct and one_h.atr_pct > 2.5:
        conf -= 0.15; cons.append(f"1h ATR {one_h.atr_pct:.2f}% high — range may break")
    if not r.liquidity.is_liquid_for_small_position:
        conf -= 0.20; cons.append("thin liquidity")

    conf = max(0.0, min(conf, 0.78))
    if conf < 0.4:
        return _none_score("range_trade", side, "any", cons)
    return StrategyScore(
        strategy="range_trade", side=side, confidence=conf,
        entry_zone=(last * Decimal("0.999"), last * Decimal("1.001")), invalidation=stop,
        take_profit_targets=tps, expected_hold_time="intraday",
        regime_fit="any", pros=tuple(pros), cons=tuple(cons),
    )


__all__ = [
    "MIN_CONFIDENCE",
    "StrategyScore",
    "StrategyRanking",
    "rank_strategies",
]
