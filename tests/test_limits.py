"""Pre-trade limits.py: each rule independently."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from scripts.limits import (
    LimitCheck,
    REENTRY_COOLDOWN_AFTER_LOSS_MINUTES,
    REENTRY_COOLDOWN_AFTER_PROFIT_MINUTES,
    _check_recent_close_cooldown,
    check_proposal,
)
from scripts.positions_store import Position, make_position_id
from scripts.safety_state import SafetyLimits, SafetyState


def _state(daily_pnl: str = "0", consec: int = 0, paused: bool = False) -> SafetyState:
    s = SafetyState()
    s.daily_pnl_usdt = Decimal(daily_pnl)
    s.consecutive_losses = consec
    s.trading_paused = paused
    if paused:
        s.paused_reason = "test"
    return s


def _open(symbol: str = "DOGEUSDT") -> Position:
    return Position(
        position_id=make_position_id(symbol),
        symbol=symbol, side="LONG", status="open",
        entry_price=Decimal("0.07654"),
        quantity=Decimal("100"), initial_quantity=Decimal("100"),
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2"), notional_usdt=Decimal("7.654"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        unrealized_pnl=Decimal("0"), realized_pnl=Decimal("0"),
        max_favorable_pnl=Decimal("0"), max_adverse_pnl=Decimal("0"),
        liquidation_price=Decimal("0.05100"),
        fees_paid_usdt=Decimal("0"), funding_paid_usdt=Decimal("0"),
        proposal_id="P", strategy="pullback_long",
        market_regime="bullish",
        opened_at="2026-05-10T12:00:00Z", updated_at="2026-05-10T12:00:00Z",
        closed_at=None, exit_price=None, exit_reason=None, mode="LIVE",
    )


def test_clean_passes():
    lc = check_proposal(
        state=_state(), limits=SafetyLimits(),
        proposed_symbol="SHIBUSDT", open_positions=[_open()], fired_this_cycle=0,
    )
    assert lc.ok


def test_paused_state_blocks():
    lc = check_proposal(
        state=_state(paused=True), limits=SafetyLimits(),
        proposed_symbol="SHIBUSDT", open_positions=[], fired_this_cycle=0,
    )
    assert not lc.ok
    assert "paused" in lc.breached


def test_daily_loss_blocks():
    lc = check_proposal(
        state=_state(daily_pnl="-1.5"), limits=SafetyLimits(daily_loss_limit_usdt=Decimal("1.5")),
        proposed_symbol="SHIBUSDT", open_positions=[], fired_this_cycle=0,
    )
    assert not lc.ok
    assert "daily_loss_limit" in lc.breached


def test_consecutive_loss_blocks():
    lc = check_proposal(
        state=_state(consec=3), limits=SafetyLimits(consecutive_loss_limit=3),
        proposed_symbol="SHIBUSDT", open_positions=[], fired_this_cycle=0,
    )
    assert not lc.ok
    assert "consecutive_loss_limit" in lc.breached


def test_max_open_positions_blocks():
    opens = [_open(symbol="A"), _open(symbol="B")]
    lc = check_proposal(
        state=_state(), limits=SafetyLimits(max_open_positions=2),
        proposed_symbol="C", open_positions=opens, fired_this_cycle=0,
    )
    assert not lc.ok
    assert "max_open_positions" in lc.breached


def test_no_duplicate_symbol_blocks():
    lc = check_proposal(
        state=_state(),
        limits=SafetyLimits(no_duplicate_symbol=True, max_open_positions=10),
        proposed_symbol="DOGEUSDT", open_positions=[_open("DOGEUSDT")],
        fired_this_cycle=0,
    )
    assert not lc.ok
    assert "no_duplicate_symbol" in lc.breached


def test_per_cycle_trade_cap_blocks():
    lc = check_proposal(
        state=_state(), limits=SafetyLimits(per_cycle_trade_cap=3),
        proposed_symbol="SHIBUSDT", open_positions=[], fired_this_cycle=3,
    )
    assert not lc.ok
    assert "per_cycle_trade_cap" in lc.breached


def test_multiple_breaches_listed_together():
    """A single proposal can trip multiple rules; all are reported."""
    lc = check_proposal(
        state=_state(consec=5, paused=True),
        limits=SafetyLimits(consecutive_loss_limit=3),
        proposed_symbol="SHIBUSDT", open_positions=[], fired_this_cycle=0,
    )
    assert not lc.ok
    assert "paused" in lc.breached
    assert "consecutive_loss_limit" in lc.breached


# ----------------------------------------------------------------------------
# Same-symbol re-entry cooldown (ENH-2026-05-11T16:55Z)
# ----------------------------------------------------------------------------


def _closed(
    symbol: str,
    *,
    exit_reason: str,
    closed_at: dt.datetime,
) -> Position:
    iso = closed_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    return Position(
        position_id=make_position_id(symbol, when=closed_at),
        symbol=symbol, side="LONG", status="closed",
        entry_price=Decimal("1.0"),
        quantity=Decimal("0"), initial_quantity=Decimal("100"),
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2"), notional_usdt=Decimal("6"),
        stop_loss=Decimal("0.95"),
        take_profit_targets=[Decimal("1.05")],
        unrealized_pnl=Decimal("0"), realized_pnl=Decimal("-0.5"),
        max_favorable_pnl=Decimal("0"), max_adverse_pnl=Decimal("-0.5"),
        liquidation_price=Decimal("0.5"),
        fees_paid_usdt=Decimal("0.01"), funding_paid_usdt=Decimal("0"),
        proposal_id="P", strategy="momentum_continuation",
        market_regime="bullish",
        opened_at=iso, updated_at=iso,
        closed_at=iso, exit_price=Decimal("0.95"), exit_reason=exit_reason,
        mode="LIVE",
    )


def test_cooldown_loss_60_min_ago_rejects():
    now = dt.datetime(2026, 5, 12, 18, 0, 0, tzinfo=dt.timezone.utc)
    closed = _closed("FOOUSDT", exit_reason="stop_loss",
                     closed_at=now - dt.timedelta(minutes=60))
    allowed, reason = _check_recent_close_cooldown(
        "FOOUSDT", [closed], now=now,
    )
    assert not allowed
    assert "re-entry cooldown" in reason
    assert "stop_loss" in reason


def test_cooldown_take_profit_60_min_ago_allows():
    """TP cooldown is 30 min — at 60 min it's expired."""
    now = dt.datetime(2026, 5, 12, 18, 0, 0, tzinfo=dt.timezone.utc)
    closed = _closed("FOOUSDT", exit_reason="take_profit",
                     closed_at=now - dt.timedelta(minutes=60))
    allowed, reason = _check_recent_close_cooldown(
        "FOOUSDT", [closed], now=now,
    )
    assert allowed
    assert reason == ""


def test_cooldown_take_profit_10_min_ago_rejects():
    now = dt.datetime(2026, 5, 12, 18, 0, 0, tzinfo=dt.timezone.utc)
    closed = _closed("FOOUSDT", exit_reason="take_profit",
                     closed_at=now - dt.timedelta(minutes=10))
    allowed, reason = _check_recent_close_cooldown(
        "FOOUSDT", [closed], now=now,
    )
    assert not allowed
    assert "take_profit" in reason


def test_cooldown_never_traded_allows():
    now = dt.datetime(2026, 5, 12, 18, 0, 0, tzinfo=dt.timezone.utc)
    other = _closed("OTHERUSDT", exit_reason="stop_loss",
                    closed_at=now - dt.timedelta(minutes=5))
    allowed, reason = _check_recent_close_cooldown(
        "FOOUSDT", [other], now=now,
    )
    assert allowed
    assert reason == ""


def test_cooldown_uses_most_recent_close():
    """Stale loss 4h ago and recent TP 5min ago — recent close governs."""
    now = dt.datetime(2026, 5, 12, 18, 0, 0, tzinfo=dt.timezone.utc)
    old_loss = _closed("FOOUSDT", exit_reason="stop_loss",
                       closed_at=now - dt.timedelta(hours=4))
    fresh_tp = _closed("FOOUSDT", exit_reason="take_profit",
                       closed_at=now - dt.timedelta(minutes=5))
    allowed, reason = _check_recent_close_cooldown(
        "FOOUSDT", [old_loss, fresh_tp], now=now,
    )
    assert not allowed
    assert "take_profit" in reason


def test_cooldown_loss_3h_ago_just_expired():
    """At exactly the window boundary, cooldown has expired."""
    now = dt.datetime(2026, 5, 12, 18, 0, 0, tzinfo=dt.timezone.utc)
    closed = _closed(
        "FOOUSDT", exit_reason="stop_loss",
        closed_at=now - dt.timedelta(minutes=REENTRY_COOLDOWN_AFTER_LOSS_MINUTES),
    )
    allowed, _ = _check_recent_close_cooldown("FOOUSDT", [closed], now=now)
    assert allowed


def test_cooldown_loss_sl_trail_locked_treated_as_loss():
    now = dt.datetime(2026, 5, 12, 18, 0, 0, tzinfo=dt.timezone.utc)
    closed = _closed("FOOUSDT", exit_reason="sl_trail_locked",
                     closed_at=now - dt.timedelta(minutes=30))
    allowed, reason = _check_recent_close_cooldown(
        "FOOUSDT", [closed], now=now,
    )
    assert not allowed
    assert "sl_trail_locked" in reason


def test_cooldown_unknown_exit_reason_does_not_block():
    """Manual / reconciliation exits aren't in either bucket — no cooldown."""
    now = dt.datetime(2026, 5, 12, 18, 0, 0, tzinfo=dt.timezone.utc)
    closed = _closed("FOOUSDT", exit_reason="manual_close_by_user_ios",
                     closed_at=now - dt.timedelta(minutes=5))
    allowed, reason = _check_recent_close_cooldown(
        "FOOUSDT", [closed], now=now,
    )
    assert allowed
    assert reason == ""


def test_cooldown_giveback_protection_is_profit_bucket():
    """30-min cooldown applies to giveback_protection_exit (came from winner)."""
    now = dt.datetime(2026, 5, 12, 18, 0, 0, tzinfo=dt.timezone.utc)
    closed = _closed("FOOUSDT", exit_reason="giveback_protection_exit",
                     closed_at=now - dt.timedelta(minutes=10))
    allowed, reason = _check_recent_close_cooldown(
        "FOOUSDT", [closed], now=now,
    )
    assert not allowed
    assert "giveback_protection_exit" in reason


def test_check_proposal_integrates_cooldown_as_soft_skip():
    """check_proposal surfaces the cooldown breach when given closed history."""
    now = dt.datetime(2026, 5, 12, 18, 0, 0, tzinfo=dt.timezone.utc)
    closed = _closed("FOOUSDT", exit_reason="stop_loss",
                     closed_at=now - dt.timedelta(minutes=30))
    lc = check_proposal(
        state=_state(),
        limits=SafetyLimits(),
        proposed_symbol="FOOUSDT",
        open_positions=[],
        fired_this_cycle=0,
        recently_closed_positions=[closed],
    )
    assert not lc.ok
    assert "reentry_cooldown" in lc.breached


def test_check_proposal_no_cooldown_param_back_compat():
    """Old callers that don't pass recently_closed_positions still work."""
    lc = check_proposal(
        state=_state(),
        limits=SafetyLimits(),
        proposed_symbol="FOOUSDT",
        open_positions=[],
        fired_this_cycle=0,
    )
    assert lc.ok
