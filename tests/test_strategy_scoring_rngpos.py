"""Strategy scoring rngpos hard-reject guard (ENH-2026-05-11T16:25Z).

These tests pin the behaviour that a directional momentum / breakout setup
must NOT be proposed when the candidate is sitting at the 24h-range extreme
on the wrong side of the trade. Today's data (BILL-1, UBUSDT-1, UBUSDT-2)
showed 3 chase entries at rngpos ≥ 0.85 each hitting full SL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace

from scripts.strategy_scoring import (
    RNGPOS_LONG_REJECT_AT_OR_ABOVE,
    RNGPOS_SHORT_REJECT_AT_OR_BELOW,
    _long_breakout,
    _momentum_continuation,
    _rngpos_24h,
    _short_breakdown,
)


# ----------------------------------------------------------------------------
# Minimal duck-typed report fixtures (avoids constructing the full
# TokenResearchReport which requires a SymbolSpec with every Binance filter).
# Each strategy under test reads attributes via `report.<field>` only, so a
# SimpleNamespace with the right shape is sufficient.
# ----------------------------------------------------------------------------


@dataclass
class _SR:
    supports: tuple = ()
    resistances: tuple = ()


@dataclass
class _TF:
    interval: str = "1h"
    candles_examined: int = 200
    last_close: Decimal = Decimal("1.0")
    ema_fast: float = 1.0
    ema_slow: float = 1.0
    ema_trend: str = "up"
    rsi_14: float = 60.0
    atr_pct: float = 1.0
    realized_vol_pct: float = 1.0
    sr: _SR = field(default_factory=_SR)
    pct_from_nearest_resistance: float | None = None
    pct_from_nearest_support: float | None = None
    last_three_close_changes_pct: tuple = (0.0, 0.0, 0.0)
    avg_volume_quote: float = 1000.0
    last_volume_quote: float = 1500.0
    volume_ratio: float = 1.5


def _make_structure(**overrides):
    base = dict(
        is_in_uptrend_1h=True,
        is_in_downtrend_1h=False,
        is_overextended_long=False,
        is_overextended_short=False,
        has_recent_pump=False,
        has_recent_dump=False,
        failed_breakout_long=False,
        failed_breakout_short=False,
        pct_from_24h_high=-1.0,
        pct_from_24h_low=5.0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_report(
    *,
    last_price: Decimal,
    high_24h: Decimal,
    low_24h: Decimal,
    one_h: _TF,
    fifteen_m: _TF,
    structure=None,
):
    return SimpleNamespace(
        symbol="TESTUSDT",
        last_price=last_price,
        ticker_24h={
            "high": str(high_24h),
            "low": str(low_24h),
            "last": str(last_price),
        },
        timeframes={"1h": one_h, "15m": fifteen_m},
        structure=structure or _make_structure(),
        no_trade_reasons=(),
    )


def _bull_uptrend_tfs() -> tuple[_TF, _TF]:
    one_h = _TF(
        interval="1h",
        last_close=Decimal("1.0"),
        ema_trend="up",
        rsi_14=60.0,
        sr=_SR(supports=(0.98,), resistances=(1.005,)),
        volume_ratio=1.6,
    )
    fifteen = _TF(
        interval="15m",
        last_close=Decimal("1.0"),
        ema_trend="up",
        rsi_14=62.0,
        sr=_SR(supports=(0.99,), resistances=(1.01,)),
        volume_ratio=1.7,
    )
    return one_h, fifteen


def _bear_downtrend_tfs() -> tuple[_TF, _TF]:
    one_h = _TF(
        interval="1h",
        last_close=Decimal("1.0"),
        ema_trend="down",
        rsi_14=38.0,
        sr=_SR(supports=(0.995,), resistances=(1.02,)),
        volume_ratio=1.6,
    )
    fifteen = _TF(
        interval="15m",
        last_close=Decimal("1.0"),
        ema_trend="down",
        rsi_14=40.0,
        sr=_SR(supports=(0.99,), resistances=(1.01,)),
        volume_ratio=1.7,
    )
    return one_h, fifteen


# ----------------------------------------------------------------------------
# _rngpos_24h helper
# ----------------------------------------------------------------------------


def test_rngpos_at_top_of_range_is_one():
    r = _make_report(
        last_price=Decimal("100"), high_24h=Decimal("100"), low_24h=Decimal("90"),
        one_h=_TF(), fifteen_m=_TF(),
    )
    assert _rngpos_24h(r) == 1.0


def test_rngpos_at_bottom_of_range_is_zero():
    r = _make_report(
        last_price=Decimal("90"), high_24h=Decimal("100"), low_24h=Decimal("90"),
        one_h=_TF(), fifteen_m=_TF(),
    )
    assert _rngpos_24h(r) == 0.0


def test_rngpos_at_midpoint_is_half():
    r = _make_report(
        last_price=Decimal("95"), high_24h=Decimal("100"), low_24h=Decimal("90"),
        one_h=_TF(), fifteen_m=_TF(),
    )
    assert _rngpos_24h(r) == 0.5


def test_rngpos_handles_flat_24h_range_without_divide_by_zero():
    """high == low — undefined range. Must return None, never raise."""
    r = _make_report(
        last_price=Decimal("100"), high_24h=Decimal("100"), low_24h=Decimal("100"),
        one_h=_TF(), fifteen_m=_TF(),
    )
    assert _rngpos_24h(r) is None


def test_rngpos_handles_missing_ticker_24h():
    r = SimpleNamespace(
        symbol="X", last_price=Decimal("1"), ticker_24h=None,
        timeframes={}, structure=_make_structure(),
    )
    assert _rngpos_24h(r) is None


def test_rngpos_handles_missing_keys():
    r = SimpleNamespace(
        symbol="X", last_price=Decimal("1"), ticker_24h={"open": "1"},
        timeframes={}, structure=_make_structure(),
    )
    # high/low missing -> TypeError on Decimal(str(None)) -> caught -> None
    assert _rngpos_24h(r) is None


def test_rngpos_threshold_constants_are_sane():
    assert 0.0 < RNGPOS_SHORT_REJECT_AT_OR_BELOW < 0.5
    assert 0.5 < RNGPOS_LONG_REJECT_AT_OR_ABOVE < 1.0


# ----------------------------------------------------------------------------
# _momentum_continuation guard
# ----------------------------------------------------------------------------


def test_momentum_continuation_rejects_long_at_rngpos_092():
    one_h, fifteen = _bull_uptrend_tfs()
    # last sits 92% up the 24h range — chase territory.
    report = _make_report(
        last_price=Decimal("1.0"),
        high_24h=Decimal("1.02"),
        low_24h=Decimal("0.78"),  # rngpos ≈ (1.0-0.78)/(1.02-0.78) ≈ 0.917
        one_h=one_h, fifteen_m=fifteen,
    )
    score = _momentum_continuation(report)
    assert score.side == "LONG"
    assert score.confidence == 0.0
    assert score.entry_zone is None
    assert any("RNGPOS_EXTREME_REJECT" in c for c in score.cons)


def test_momentum_continuation_allows_long_at_rngpos_050():
    one_h, fifteen = _bull_uptrend_tfs()
    # Midpoint of 24h range — fine, existing logic applies.
    report = _make_report(
        last_price=Decimal("1.0"),
        high_24h=Decimal("1.10"),
        low_24h=Decimal("0.90"),  # rngpos = 0.50
        one_h=one_h, fifteen_m=fifteen,
    )
    score = _momentum_continuation(report)
    assert score.side == "LONG"
    assert score.confidence > 0
    assert score.entry_zone is not None
    assert not any("RNGPOS_EXTREME_REJECT" in c for c in score.cons)


def test_momentum_continuation_rejects_short_at_rngpos_008():
    one_h, fifteen = _bear_downtrend_tfs()
    report = _make_report(
        last_price=Decimal("1.0"),
        high_24h=Decimal("1.20"),
        low_24h=Decimal("0.99"),  # rngpos = (1.0-0.99)/0.21 ≈ 0.048
        one_h=one_h, fifteen_m=fifteen,
    )
    score = _momentum_continuation(report)
    assert score.side == "SHORT"
    assert score.confidence == 0.0
    assert any("RNGPOS_EXTREME_REJECT" in c for c in score.cons)


def test_momentum_continuation_allows_short_at_rngpos_050():
    one_h, fifteen = _bear_downtrend_tfs()
    report = _make_report(
        last_price=Decimal("1.0"),
        high_24h=Decimal("1.10"),
        low_24h=Decimal("0.90"),  # rngpos = 0.50
        one_h=one_h, fifteen_m=fifteen,
    )
    score = _momentum_continuation(report)
    assert score.side == "SHORT"
    assert score.confidence > 0
    assert score.entry_zone is not None


def test_momentum_continuation_fails_open_on_missing_24h_data():
    """No ticker_24h -> rngpos None -> existing strategy logic proceeds.

    The rngpos gate is a *guard*, not a precondition. Missing data must not
    silently let a chase through, but it also must not block every entry
    just because the 24h feed glitched.
    """
    one_h, fifteen = _bull_uptrend_tfs()
    report = SimpleNamespace(
        symbol="X",
        last_price=Decimal("1.0"),
        ticker_24h=None,
        timeframes={"1h": one_h, "15m": fifteen},
        structure=_make_structure(),
        no_trade_reasons=(),
    )
    score = _momentum_continuation(report)
    assert score.side == "LONG"
    # Existing logic still runs; we do NOT expect a RNGPOS reject reason.
    assert not any("RNGPOS_EXTREME_REJECT" in c for c in score.cons)


# ----------------------------------------------------------------------------
# _long_breakout / _short_breakdown guards
# ----------------------------------------------------------------------------


def test_long_breakout_rejects_at_rngpos_090():
    one_h, fifteen = _bull_uptrend_tfs()
    report = _make_report(
        last_price=Decimal("1.0"),
        high_24h=Decimal("1.02"),
        low_24h=Decimal("0.80"),  # rngpos ≈ 0.909
        one_h=one_h, fifteen_m=fifteen,
    )
    score = _long_breakout(report)
    assert score.confidence == 0.0
    assert any("RNGPOS_EXTREME_REJECT" in c for c in score.cons)


def test_short_breakdown_rejects_at_rngpos_010():
    one_h, fifteen = _bear_downtrend_tfs()
    report = _make_report(
        last_price=Decimal("1.0"),
        high_24h=Decimal("1.20"),
        low_24h=Decimal("0.98"),  # rngpos ≈ 0.091
        one_h=one_h, fifteen_m=fifteen,
    )
    score = _short_breakdown(report)
    assert score.confidence == 0.0
    assert any("RNGPOS_EXTREME_REJECT" in c for c in score.cons)
