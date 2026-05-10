"""Risk engine math: sizing, liquidation, fee-aware profit."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.risk_engine import (
    DEFAULT_TAKER_FEE,
    RiskConfig,
    estimate_liquidation_isolated,
    estimate_profit,
    evaluate_proposal,
    size_from_risk,
)
from scripts.symbol_filters import parse_symbol_spec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def doge_spec():
    raw = {
        "symbol": "DOGEUSDT", "pair": "DOGEUSDT", "contractType": "PERPETUAL",
        "status": "TRADING", "baseAsset": "DOGE", "quoteAsset": "USDT",
        "pricePrecision": 5, "quantityPrecision": 0,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.00001",
             "maxPrice": "1000", "tickSize": "0.00001"},
            {"filterType": "LOT_SIZE", "minQty": "1", "maxQty": "10000000", "stepSize": "1"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "1", "maxQty": "5900000", "stepSize": "1"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
            {"filterType": "PERCENT_PRICE", "multiplierUp": "1.15",
             "multiplierDown": "0.85", "multiplierDecimal": "4"},
        ],
    }
    return parse_symbol_spec(raw)


# ---------------------------------------------------------------------------
# Liquidation
# ---------------------------------------------------------------------------


def test_liquidation_long_3x_far_enough():
    """LONG @ 100 with 3x and 0.5% MMR: liq ≈ 100 * (1 - 1/3 + 0.005) = 67.17."""
    est = estimate_liquidation_isolated(side="LONG", entry_price=Decimal("100"), leverage=3)
    assert est.liquidation_price == pytest.approx(Decimal("67.17"), abs=Decimal("0.05"))
    # Distance ≈ 32.83% — passes the default 30% requirement.
    assert est.distance_pct > Decimal("30")
    assert est.is_safe is True


def test_liquidation_long_20x_too_close():
    """20x leverage gives ~5% liquidation distance — must fail the 30% rule."""
    est = estimate_liquidation_isolated(side="LONG", entry_price=Decimal("100"), leverage=20)
    assert est.distance_pct < Decimal("10")
    assert est.is_safe is False


def test_liquidation_short_3x():
    """SHORT @ 100, 3x: liq ≈ 100 * (1 + 1/3 - 0.005) = 132.83."""
    est = estimate_liquidation_isolated(side="SHORT", entry_price=Decimal("100"), leverage=3)
    assert est.liquidation_price == pytest.approx(Decimal("132.83"), abs=Decimal("0.05"))
    assert est.is_safe is True


def test_liquidation_invalid_inputs():
    with pytest.raises(ValueError):
        estimate_liquidation_isolated(side="HEDGE", entry_price=Decimal("100"), leverage=3)
    with pytest.raises(ValueError):
        estimate_liquidation_isolated(side="LONG", entry_price=Decimal("100"), leverage=0)


# ---------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------


def test_sizing_respects_max_loss(doge_spec):
    # max_loss=0.20 USDT, entry 0.07654, stop 0.07500 (1.54 % away).
    # We need max_loss generous enough to (a) exceed the qty-step rounding
    # boundary AND (b) absorb the MIN_NOTIONAL bump-up (5 USDT / 0.07654 ≈ 66
    # qty → loss ≈ 0.10 + fees).
    s = size_from_risk(
        doge_spec, side="LONG",
        entry_price=Decimal("0.07654"), stop_price=Decimal("0.07500"),
        max_loss_usdt=Decimal("0.20"), leverage=3,
    )
    # Loss at stop (excluding round-trip fees, which are tracked separately)
    # must be ≤ max_loss.
    risk_per_unit = Decimal("0.07654") - Decimal("0.07500")
    actual_loss = risk_per_unit * s.quantity
    fees_round_trip = s.notional_usdt * DEFAULT_TAKER_FEE * Decimal("2")
    assert actual_loss + fees_round_trip <= Decimal("0.21")
    assert s.notional_usdt >= Decimal("5"), "must satisfy MIN_NOTIONAL"
    assert not s.breaches, s.breaches


def test_sizing_returns_breach_when_min_notional_exceeds_budget(doge_spec):
    """Tight stop + small budget + MIN_NOTIONAL=5 → breach with clear reason."""
    s = size_from_risk(
        doge_spec, side="LONG",
        entry_price=Decimal("0.07654"), stop_price=Decimal("0.07500"),
        max_loss_usdt=Decimal("0.05"),  # too small to absorb min-qty bump
        leverage=3,
    )
    assert s.quantity == 0
    assert any("MIN_NOTIONAL" in b for b in s.breaches)


def test_sizing_rejects_stop_on_wrong_side(doge_spec):
    s = size_from_risk(
        doge_spec, side="LONG",
        entry_price=Decimal("100"), stop_price=Decimal("110"),  # wrong side
        max_loss_usdt=Decimal("1"), leverage=3,
    )
    assert s.quantity == 0
    assert any("wrong side" in b for b in s.breaches)


def test_sizing_qty_rounds_to_zero_returns_breach(doge_spec):
    """If max-loss is so small that qty rounds to 0 at stepSize, return breach."""
    s = size_from_risk(
        doge_spec, side="LONG",
        entry_price=Decimal("0.07654"), stop_price=Decimal("0.07500"),
        max_loss_usdt=Decimal("0.0001"), leverage=3,
    )
    assert s.quantity == 0
    assert any("rounds to 0" in b for b in s.breaches)


# ---------------------------------------------------------------------------
# Profit
# ---------------------------------------------------------------------------


def test_profit_meaningful_long():
    p = estimate_profit(
        side="LONG",
        entry_price=Decimal("100"), take_profit_price=Decimal("103"),
        stop_price=Decimal("99"), quantity=Decimal("0.1"),
        margin_usdt=Decimal("3.33"),       # ~3x leverage on 10 notional
    )
    assert p.gross_profit_usdt == pytest.approx(Decimal("0.3"), abs=Decimal("0.001"))
    assert p.risk_reward_ratio == pytest.approx(Decimal("3"), abs=Decimal("0.001"))
    assert p.net_profit_usdt > 0
    assert p.is_meaningful is True


def test_profit_eaten_by_fees():
    """A tiny TP barely above entry should fail meaningfulness."""
    p = estimate_profit(
        side="LONG",
        entry_price=Decimal("100"), take_profit_price=Decimal("100.05"),
        stop_price=Decimal("99.5"), quantity=Decimal("0.1"),
        margin_usdt=Decimal("3.33"),
    )
    # Gross 0.005; fees on 100*0.1*2*0.0005 = 0.01 → already negative net.
    assert p.is_meaningful is False


# ---------------------------------------------------------------------------
# evaluate_proposal end-to-end
# ---------------------------------------------------------------------------


def test_evaluate_proposal_approves_clean_setup(doge_spec):
    # 2 USDT margin × 8% max-loss budget = 0.16 USDT, enough to absorb the
    # MIN_NOTIONAL bump-up at this price/stop combo. Realistic for the
    # user's 10 USDT wallet.
    approval = evaluate_proposal(
        proposal_id="TEST-001",
        spec=doge_spec,
        side="LONG",
        entry_price=Decimal("0.07654"),
        stop_price=Decimal("0.07500"),
        take_profit_price=Decimal("0.07900"),
        cfg=RiskConfig(
            max_margin_per_trade_usdt=Decimal("2"),
            default_margin_per_trade_usdt=Decimal("2"),
            default_leverage=3,
            max_planned_loss_pct_of_margin=Decimal("0.08"),
        ),
    )
    assert approval.risk_decision == "approved", approval.risk_reason
    assert approval.liquidation_distance_ok
    assert approval.fee_profit_ok


def test_evaluate_proposal_rejects_high_leverage_close_liq(doge_spec):
    approval = evaluate_proposal(
        proposal_id="TEST-002",
        spec=doge_spec,
        side="LONG",
        entry_price=Decimal("0.07654"),
        stop_price=Decimal("0.07500"),
        take_profit_price=Decimal("0.07900"),
        cfg=RiskConfig(
            default_leverage=20, max_leverage=20,
            default_margin_per_trade_usdt=Decimal("2"),
            max_margin_per_trade_usdt=Decimal("2"),
            max_planned_loss_pct_of_margin=Decimal("0.08"),
        ),
        desired_leverage=20,
    )
    assert approval.risk_decision == "lower_leverage"
    assert not approval.liquidation_distance_ok


def test_evaluate_proposal_rejects_when_fees_eat_profit(doge_spec):
    """TP only 0.5 % above entry — fees consume the move."""
    approval = evaluate_proposal(
        proposal_id="TEST-003",
        spec=doge_spec,
        side="LONG",
        entry_price=Decimal("0.07654"),
        stop_price=Decimal("0.07500"),
        take_profit_price=Decimal("0.07692"),  # +0.5 %
        cfg=RiskConfig(
            default_margin_per_trade_usdt=Decimal("2"),
            max_margin_per_trade_usdt=Decimal("2"),
            max_planned_loss_pct_of_margin=Decimal("0.08"),
        ),
    )
    assert approval.risk_decision == "rejected"
    assert not approval.fee_profit_ok
