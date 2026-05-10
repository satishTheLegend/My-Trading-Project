"""Pre-trade limits.py: each rule independently."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.limits import LimitCheck, check_proposal
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
