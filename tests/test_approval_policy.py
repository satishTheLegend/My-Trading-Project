"""Approval policy: boundary cases, defensive rules."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.approval_policy import ApprovalPolicy, evaluate


def _ok(notional: str = "10") -> dict:
    """Defaults that don't trip any defensive rule."""
    return {
        "mode": "SEMI_AUTO_LIVE",
        "notional_usdt": Decimal(notional),
        "leverage": 3,
        "daily_pnl_usdt": Decimal("0"),
        "daily_loss_limit_usdt": Decimal("1.5"),
        "is_first_live_trade_of_session": False,
    }


# ---------------------------------------------------------------------------
# Mode handling
# ---------------------------------------------------------------------------


def test_paper_never_requires_approval():
    d = evaluate(**{**_ok(notional="10000"), "mode": "PAPER_TRADING"})
    assert not d.requires_user_approval


def test_full_auto_never_requires_approval():
    d = evaluate(**{**_ok(notional="10000"), "mode": "FULL_AUTO_LIVE"})
    assert not d.requires_user_approval


# ---------------------------------------------------------------------------
# $50 threshold boundary
# ---------------------------------------------------------------------------


def test_below_threshold_auto_fires():
    d = evaluate(**_ok(notional="49.99"))
    assert not d.requires_user_approval
    assert "auto-approve" in d.reason


def test_at_threshold_auto_fires():
    """Exactly $50 still auto-fires; >$50 triggers."""
    d = evaluate(**_ok(notional="50"))
    assert not d.requires_user_approval


def test_above_threshold_requires_approval():
    d = evaluate(**_ok(notional="50.01"))
    assert d.requires_user_approval
    assert "notional_above_threshold" in d.triggered_rules


def test_custom_threshold_respected():
    pol = ApprovalPolicy(notional_threshold_usdt=Decimal("100"))
    d = evaluate(**_ok(notional="75"), policy=pol)
    assert not d.requires_user_approval
    d2 = evaluate(**_ok(notional="125"), policy=pol)
    assert d2.requires_user_approval


# ---------------------------------------------------------------------------
# Defensive rules
# ---------------------------------------------------------------------------


def test_first_live_trade_always_asks_even_for_small_notional():
    d = evaluate(**{**_ok(notional="5"), "is_first_live_trade_of_session": True})
    assert d.requires_user_approval
    assert "first_live_trade_of_session" in d.triggered_rules


def test_daily_loss_consumption_above_75pct_triggers():
    # daily_pnl = -1.2 with limit 1.5 → 80% consumption → trigger
    d = evaluate(**{
        **_ok(notional="5"),
        "daily_pnl_usdt": Decimal("-1.2"),
        "daily_loss_limit_usdt": Decimal("1.5"),
    })
    assert d.requires_user_approval
    assert "daily_loss_consumption_high" in d.triggered_rules


def test_daily_loss_consumption_below_threshold_does_not_trigger():
    # daily_pnl = -0.5 with limit 1.5 → 33% consumption → no trigger
    d = evaluate(**{
        **_ok(notional="5"),
        "daily_pnl_usdt": Decimal("-0.5"),
        "daily_loss_limit_usdt": Decimal("1.5"),
    })
    assert not d.requires_user_approval


def test_high_leverage_flagged_but_does_not_by_itself_trigger():
    d = evaluate(**{**_ok(notional="5"), "leverage": 10})
    # Only the flag rule, no approval-triggering rule fires.
    assert "high_leverage_flag" in d.triggered_rules
    assert not d.requires_user_approval


def test_combo_above_threshold_and_first_trade_lists_both_reasons():
    d = evaluate(**{
        **_ok(notional="100"),
        "is_first_live_trade_of_session": True,
    })
    assert d.requires_user_approval
    assert "notional_above_threshold" in d.triggered_rules
    assert "first_live_trade_of_session" in d.triggered_rules
