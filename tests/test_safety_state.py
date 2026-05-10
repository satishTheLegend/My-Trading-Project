"""SafetyState: rollover, breach detection, pause/resume."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.safety_state import (
    SafetyLimits, SafetyState, SafetyStateManager,
)


@pytest.fixture
def manager(tmp_path: Path) -> SafetyStateManager:
    return SafetyStateManager(
        risk_state_path=tmp_path / "risk-state.json",
        system_health_path=tmp_path / "system-health.json",
        limits=SafetyLimits(
            daily_loss_limit_usdt=Decimal("1.5"),
            consecutive_loss_limit=3,
            cooldown_minutes_after_consecutive_losses=60,
        ),
    )


def test_load_default_when_no_file(manager):
    state = manager.load()
    assert state.daily_pnl_usdt == Decimal("0")
    assert state.consecutive_losses == 0
    assert state.trading_paused is False


def test_save_and_reload_roundtrip(manager):
    state = manager.load()
    state.daily_pnl_usdt = Decimal("-0.5")
    state.consecutive_losses = 2
    manager.save(state)
    again = manager.load()
    assert again.daily_pnl_usdt == Decimal("-0.5")
    assert again.consecutive_losses == 2


# -- rollover ---------------------------------------------------------------


def test_rollover_zeros_daily_pnl_on_new_utc_day(manager):
    state = manager.load()
    state.daily_pnl_usdt = Decimal("-0.7")
    state.daily_period_start = "1999-01-01"   # ancient → forces rollover
    state.trades_today = 4
    manager.save(state)
    new_state, did = manager.perform_daily_rollover_if_needed()
    assert did
    assert new_state.daily_pnl_usdt == Decimal("0")
    assert new_state.trades_today == 0
    # last_period archived.
    assert new_state.last_period.get("daily_pnl_usdt") == "-0.7"
    assert new_state.last_period.get("trades_count") == 4


def test_rollover_noop_when_same_day(manager):
    state = manager.load()
    today = dt.datetime.utcnow().date().isoformat()
    state.daily_period_start = today
    state.daily_pnl_usdt = Decimal("-0.1")
    manager.save(state)
    new_state, did = manager.perform_daily_rollover_if_needed()
    assert not did
    assert new_state.daily_pnl_usdt == Decimal("-0.1")


def test_rollover_clears_soft_pause(manager):
    state = manager.load()
    state.daily_period_start = "1999-01-01"
    state.trading_paused = True
    state.paused_reason = "yesterday's daily-loss breach"
    state.pause_carry_over_rollover = False
    manager.save(state)
    new_state, did = manager.perform_daily_rollover_if_needed()
    assert did
    assert not new_state.trading_paused


def test_rollover_keeps_carryover_pause(manager):
    state = manager.load()
    state.daily_period_start = "1999-01-01"
    state.trading_paused = True
    state.paused_reason = "withdrawal permission detected"
    state.pause_carry_over_rollover = True
    manager.save(state)
    new_state, did = manager.perform_daily_rollover_if_needed()
    assert did
    assert new_state.trading_paused
    assert new_state.pause_carry_over_rollover


# -- record_trade_close -----------------------------------------------------


def test_winning_trade_resets_consecutive_losses(manager):
    state = manager.load()
    state.consecutive_losses = 2
    manager.save(state)
    new_state = manager.record_trade_close(net_pnl_usdt=Decimal("0.20"))
    assert new_state.consecutive_losses == 0
    assert new_state.consecutive_wins == 1
    assert new_state.daily_pnl_usdt == Decimal("0.20")


def test_losing_trade_increments_consecutive(manager):
    new_state = manager.record_trade_close(net_pnl_usdt=Decimal("-0.10"))
    assert new_state.consecutive_losses == 1
    assert new_state.consecutive_wins == 0


def test_consecutive_loss_breach_pauses_with_cooldown(manager):
    # Three losses in a row → breach.
    manager.record_trade_close(net_pnl_usdt=Decimal("-0.10"))
    manager.record_trade_close(net_pnl_usdt=Decimal("-0.10"))
    state = manager.record_trade_close(net_pnl_usdt=Decimal("-0.10"))
    assert state.trading_paused
    assert "consecutive losses" in (state.paused_reason or "")
    # Cooldown window set.
    assert state.paused_until_iso is not None


def test_daily_loss_breach_pauses_without_cooldown(manager):
    # One huge loss → breach (>1.5 USDT loss).
    state = manager.record_trade_close(net_pnl_usdt=Decimal("-2.0"))
    assert state.trading_paused
    assert "daily loss" in (state.paused_reason or "")
    # No cooldown — daily-loss pauses last until rollover or manual resume.
    assert state.paused_until_iso is None


# -- check_can_trade --------------------------------------------------------


def test_check_can_trade_paused_returns_false(manager):
    manager.record_trade_close(net_pnl_usdt=Decimal("-2.0"))   # daily breach
    state, can, why = manager.check_can_trade()
    assert not can
    assert "daily loss" in why


def test_check_can_trade_auto_resumes_after_cooldown(manager):
    # Pause with a deadline already in the past.
    state = manager.load()
    state.trading_paused = True
    state.paused_reason = "consec breach"
    state.paused_until_iso = (
        dt.datetime.utcnow() - dt.timedelta(minutes=1)
    ).isoformat(timespec="seconds") + "Z"
    manager.save(state)
    new_state, can, why = manager.check_can_trade(force_rollover_check=False)
    assert can
    assert "cooldown" in why.lower()
    # Pause flag cleared.
    assert not new_state.trading_paused


# -- pause / resume ---------------------------------------------------------


def test_manual_pause_then_resume(manager):
    state = manager.pause("test reason", until_minutes=10)
    assert state.trading_paused
    assert state.paused_reason == "test reason"
    assert state.paused_until_iso is not None
    state2 = manager.resume()
    assert not state2.trading_paused
    assert state2.paused_reason is None


def test_reset_daily_zeros_counters(manager):
    manager.record_trade_close(net_pnl_usdt=Decimal("-0.5"))
    state = manager.reset_daily_counters()
    assert state.daily_pnl_usdt == Decimal("0")
    assert state.trades_today == 0
