"""Exit simulator: every decision branch."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.exit_simulator import (
    DECISION_EMERGENCY_EXIT,
    DECISION_FULL_TP,
    DECISION_HOLD,
    DECISION_INVALIDATION_EXIT,
    DECISION_PARTIAL_TP,
    DECISION_STOP_HIT,
    DECISION_TRAIL_STOP,
    apply_decision,
    decide_from_candle,
)
from scripts.market_data import Candle
from scripts.positions_store import Position, make_position_id


def _candle(o: float, h: float, l: float, c: float, t: int = 0) -> Candle:
    return Candle(
        open_time_ms=t, open=Decimal(str(o)), high=Decimal(str(h)),
        low=Decimal(str(l)), close=Decimal(str(c)),
        volume=Decimal("1000"), close_time_ms=t + 60_000,
        quote_volume=Decimal(str(1000 * c)), trades=10,
        taker_buy_base_volume=Decimal("500"),
        taker_buy_quote_volume=Decimal(str(500 * c)),
    )


def _pos(side: str = "LONG", entry: str = "0.07654", stop: str = "0.07500",
         tps=("0.07800", "0.07900", "0.08000"), qty: str = "100") -> Position:
    return Position(
        position_id=make_position_id("DOGEUSDT"),
        symbol="DOGEUSDT", side=side, status="open",
        entry_price=Decimal(entry),
        quantity=Decimal(qty), initial_quantity=Decimal(qty),
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2"), notional_usdt=Decimal(entry) * Decimal(qty),
        stop_loss=Decimal(stop),
        take_profit_targets=[Decimal(t) for t in tps],
        unrealized_pnl=Decimal("0"), realized_pnl=Decimal("0"),
        max_favorable_pnl=Decimal("0"), max_adverse_pnl=Decimal("0"),
        liquidation_price=Decimal("0.05100"),
        fees_paid_usdt=Decimal("0"), funding_paid_usdt=Decimal("0"),
        proposal_id="PROP-T", strategy="pullback_long",
        market_regime="bullish",
        opened_at="2026-05-10T12:00:00Z", updated_at="2026-05-10T12:00:00Z",
        closed_at=None, exit_price=None, exit_reason=None, mode="PAPER_TRADING",
    )


# ---------------------------------------------------------------------------
# decide_from_candle
# ---------------------------------------------------------------------------


def test_hold_when_inside_range():
    pos = _pos()
    bar = _candle(0.07650, 0.07670, 0.07640, 0.07660)
    d = decide_from_candle(pos, bar)
    assert d.decision == DECISION_HOLD


def test_stop_hit_long_when_low_breaches_stop():
    pos = _pos()
    bar = _candle(0.07600, 0.07620, 0.07480, 0.07550)
    d = decide_from_candle(pos, bar)
    assert d.decision == DECISION_STOP_HIT
    assert d.is_terminal
    assert d.fill_price == pos.stop_loss


def test_stop_hit_short_when_high_breaches_stop():
    pos = _pos(side="SHORT", entry="0.07654", stop="0.07800",
               tps=("0.07500", "0.07400", "0.07300"))
    bar = _candle(0.07700, 0.07810, 0.07690, 0.07750)
    d = decide_from_candle(pos, bar)
    assert d.decision == DECISION_STOP_HIT


def test_full_tp_long():
    pos = _pos()
    bar = _candle(0.07700, 0.08010, 0.07690, 0.07950)
    d = decide_from_candle(pos, bar)
    assert d.decision == DECISION_FULL_TP
    assert d.is_terminal


def test_partial_tp_long():
    pos = _pos()
    bar = _candle(0.07700, 0.07810, 0.07690, 0.07750)
    d = decide_from_candle(pos, bar)
    assert d.decision == DECISION_PARTIAL_TP
    assert not d.is_terminal
    assert d.qty_to_close < pos.quantity
    assert d.new_stop_loss == pos.entry_price       # moved to breakeven


def test_stop_priority_over_tp_in_same_bar():
    """If a single bar's range covers both stop AND TP, we assume stop fills first."""
    pos = _pos()
    bar = _candle(0.07650, 0.07810, 0.07490, 0.07700)   # tagged 0.07810 AND 0.07490
    d = decide_from_candle(pos, bar)
    assert d.decision == DECISION_STOP_HIT


def test_emergency_exit_overrides_everything():
    pos = _pos()
    bar = _candle(0.07650, 0.07670, 0.07640, 0.07660)
    d = decide_from_candle(pos, bar, safety_emergency=True)
    assert d.decision == DECISION_EMERGENCY_EXIT
    assert d.is_terminal


def test_invalidation_reason_triggers_exit_when_no_stop_or_tp_hit():
    pos = _pos()
    bar = _candle(0.07650, 0.07670, 0.07640, 0.07660)
    d = decide_from_candle(pos, bar, invalidation_reason="BTC dumped 3% in 5m")
    assert d.decision == DECISION_INVALIDATION_EXIT


def test_trail_stop_ratchets_long_after_favorable_move():
    pos = _pos(stop="0.07500")
    # bar.high - entry = 0.00046. Need that >= 2 × ATR. ATR=0.0001 → trigger
    # 0.0002, easily cleared. Proposed new stop = 0.07700 - 1.2×0.0001 =
    # 0.076988, well above pos.stop_loss=0.07500 → trail fires.
    bar = _candle(0.07650, 0.07700, 0.07640, 0.07695)
    d = decide_from_candle(pos, bar, atr_value=Decimal("0.0001"))
    assert d.decision == DECISION_TRAIL_STOP
    assert d.new_stop_loss is not None and d.new_stop_loss > pos.stop_loss


# ---------------------------------------------------------------------------
# apply_decision
# ---------------------------------------------------------------------------


def test_apply_stop_hit_closes_position_and_realizes_loss():
    pos = _pos()
    bar = _candle(0.07600, 0.07620, 0.07480, 0.07550)
    d = decide_from_candle(pos, bar)
    applied = apply_decision(pos, d)
    assert pos.status == "closed"
    assert pos.exit_price == pos.stop_loss
    assert pos.quantity == 0
    assert pos.realized_pnl < 0


def test_apply_partial_tp_keeps_remaining_qty_and_moves_stop():
    pos = _pos()
    bar = _candle(0.07700, 0.07810, 0.07690, 0.07750)
    d = decide_from_candle(pos, bar)
    initial_qty = pos.quantity
    applied = apply_decision(pos, d)
    assert pos.status == "partial_exit"
    assert pos.quantity > 0 and pos.quantity < initial_qty
    assert pos.stop_loss == pos.entry_price          # breakeven
    # The partial TP is recorded in notes so we don't re-trigger it next bar.
    assert any("partial_tp_at:" in n for n in pos.notes)


def test_partial_tp_idempotent_within_same_bar_run():
    """After applying partial TP, the same target shouldn't re-fire next call."""
    pos = _pos()
    bar = _candle(0.07700, 0.07810, 0.07690, 0.07750)
    d1 = decide_from_candle(pos, bar)
    apply_decision(pos, d1)
    d2 = decide_from_candle(pos, bar)
    assert d2.decision != DECISION_PARTIAL_TP   # already taken — should not re-trigger
