"""profit_protection: each branch fires correctly + never hides losses."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.market_data import Candle
from scripts.positions_store import Position, make_position_id
from scripts.profit_protection import (
    ProfitProtectionConfig,
    advise,
)


def _candle(price: float, t: int = 0) -> Candle:
    p = Decimal(str(price))
    return Candle(
        open_time_ms=t, open=p, high=p * Decimal("1.001"),
        low=p * Decimal("0.999"), close=p,
        volume=Decimal("1000"), close_time_ms=t + 60_000,
        quote_volume=Decimal("1000") * p, trades=10,
        taker_buy_base_volume=Decimal("500"),
        taker_buy_quote_volume=Decimal("500") * p,
    )


def _pos(side: str = "LONG", entry: str = "0.07654", stop: str = "0.07500",
         qty: str = "100", margin: str = "2") -> Position:
    return Position(
        position_id=make_position_id("DOGEUSDT"),
        symbol="DOGEUSDT", side=side, status="open",
        entry_price=Decimal(entry),
        quantity=Decimal(qty), initial_quantity=Decimal(qty),
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal(margin),
        notional_usdt=Decimal(entry) * Decimal(qty),
        stop_loss=Decimal(stop),
        take_profit_targets=[Decimal("0.07800")],
        unrealized_pnl=Decimal("0"), realized_pnl=Decimal("0"),
        max_favorable_pnl=Decimal("0"), max_adverse_pnl=Decimal("0"),
        liquidation_price=Decimal("0.05100"),
        fees_paid_usdt=Decimal("0"), funding_paid_usdt=Decimal("0"),
        proposal_id="PROP-T", strategy="pullback_long",
        market_regime="bullish",
        opened_at="2026-05-10T12:00:00Z", updated_at="2026-05-10T12:00:00Z",
        closed_at=None, exit_price=None, exit_reason=None, mode="LIVE",
    )


def test_hold_when_modestly_in_profit_below_threshold():
    pos = _pos()                       # entry 0.07654, stop 0.07500
    bar = _candle(0.07670)             # ~0.21% in profit, well below 1R
    a = advise(pos, bar)
    assert a.action == "hold"


def test_move_breakeven_at_1r_profit():
    pos = _pos()                       # 1R risk per unit = 0.00154
    # Move price to entry + 1R = 0.07808.
    bar = _candle(0.07808)
    a = advise(pos, bar)
    assert a.action == "move_breakeven"
    assert a.suggested_new_stop == pos.entry_price


def test_partial_take_profit_at_1_5r():
    pos = _pos()
    bar = _candle(0.07885)             # entry + 1.5R ≈ 0.07885
    a = advise(pos, bar)
    assert a.action == "partial_take_profit"
    assert a.suggested_close_qty is not None
    assert a.suggested_close_qty <= pos.quantity
    assert a.suggested_new_stop == pos.entry_price


def test_no_double_partial_after_already_taken():
    pos = _pos()
    pos.notes.append("partial_tp_at:0.07800")
    bar = _candle(0.07900)
    a = advise(pos, bar)
    assert a.action != "partial_take_profit"


def test_exit_now_when_giveback_and_back_below_entry():
    pos = _pos()
    pos.max_favorable_pnl = Decimal("0.20")    # MFE = 0.20 USDT
    bar = _candle(0.07640)             # below entry 0.07654 → unreal < 0
    a = advise(pos, bar)
    assert a.action == "exit_now"
    assert a.suggested_close_qty == pos.quantity
    assert "give back" in a.reason.lower() or "gave back" in a.reason.lower()


def test_tighten_stop_on_meaningful_pullback_still_in_profit():
    """For tighten_stop to fire, partial_tp must already be taken AND stop
    must already be at/above breakeven (so move_breakeven won't re-fire).
    """
    pos = _pos()
    pos.notes.append("partial_tp_at:0.07800")    # partial already taken
    pos.stop_loss = pos.entry_price              # already at breakeven
    pos.max_favorable_pnl = Decimal("0.20")

    # bar at 0.07700 → unreal = (0.07700-0.07654)*100 = 0.046 USDT (in profit)
    # pullback from MFE = (0.20-0.046)/0.20 ≈ 77 %  — between 50 and 100.
    # exit_now requires unreal <= 0 → not us, so we land in tighten_stop.
    bar = _candle(0.07700)
    a = advise(pos, bar)
    assert a.action == "tighten_stop", f"got {a.action}: {a.reason}"
    assert a.suggested_new_stop is not None
    assert a.suggested_new_stop > pos.stop_loss


def test_exit_now_when_loss_at_80pct_of_planned():
    pos = _pos(margin="2")             # planned max loss = 5% of 2 = 0.10
    pos.max_favorable_pnl = Decimal("0")
    # We need unreal ≤ -0.08 (80% of 0.10). Per-unit loss = entry-mark.
    # 100 qty × (0.07654 - 0.07574) = 0.08
    bar = _candle(0.07574)
    a = advise(pos, bar)
    assert a.action == "exit_now"
    assert "max loss" in a.reason.lower()


def test_short_side_partial_tp_uses_correct_direction():
    pos = _pos(side="SHORT", entry="0.07654", stop="0.07800")
    # 1.5R below entry = 0.07654 - 1.5*0.00146 = ~0.07435
    bar = _candle(0.07435)
    a = advise(pos, bar)
    assert a.action == "partial_take_profit"
    assert a.suggested_new_stop == pos.entry_price


def test_never_recommend_widening_stop_or_averaging_down():
    """Sanity guard: every action returned must be from the safe set."""
    safe_actions = {
        "hold", "partial_take_profit", "tighten_stop",
        "move_breakeven", "exit_now",
    }
    pos = _pos()
    for price in (0.06000, 0.07000, 0.07500, 0.07654, 0.07700, 0.07800,
                  0.07900, 0.08000, 0.08500, 0.10000):
        bar = _candle(price)
        a = advise(pos, bar)
        assert a.action in safe_actions, f"unsafe action {a.action} at price {price}"
