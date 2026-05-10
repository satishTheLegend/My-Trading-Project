"""Position Manager: pure reconciliation logic. No HTTP."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.account import ExchangePosition
from scripts.position_manager import reconcile
from scripts.positions_store import Position, make_position_id


def _local(symbol: str = "DOGEUSDT", side: str = "LONG", qty: str = "100",
           status: str = "open") -> Position:
    return Position(
        position_id=make_position_id(symbol),
        symbol=symbol, side=side, status=status,
        entry_price=Decimal("0.07654"),
        quantity=Decimal(qty), initial_quantity=Decimal(qty),
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2"), notional_usdt=Decimal("7.654"),
        stop_loss=Decimal("0.07500"),
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


def _exch(symbol: str = "DOGEUSDT", amt: str = "100", entry: str = "0.07654") -> ExchangePosition:
    return ExchangePosition(
        symbol=symbol, position_amt=Decimal(amt),
        entry_price=Decimal(entry), mark_price=Decimal(entry),
        un_realized_profit=Decimal("0"),
        leverage=3, margin_type="isolated",
        isolated_wallet=Decimal("2"),
        liquidation_price=Decimal("0.05100"),
        update_time_ms=0,
    )


def test_clean_match():
    rep = reconcile(local_positions=[_local()], exchange_positions=[_exch()])
    assert rep.is_clean
    assert rep.matched == 1
    assert rep.local_open_count == 1 and rep.exchange_open_count == 1


def test_missing_on_exchange():
    rep = reconcile(local_positions=[_local()], exchange_positions=[])
    assert not rep.is_clean
    assert rep.mismatches[0].kind == "missing_on_exchange"
    assert rep.mismatches[0].symbol == "DOGEUSDT"


def test_missing_locally():
    rep = reconcile(local_positions=[], exchange_positions=[_exch(symbol="SHIBUSDT")])
    assert not rep.is_clean
    assert rep.mismatches[0].kind == "missing_locally"


def test_qty_mismatch():
    rep = reconcile(
        local_positions=[_local(qty="100")],
        exchange_positions=[_exch(amt="50")],
    )
    assert not rep.is_clean
    assert rep.mismatches[0].kind == "qty_mismatch"


def test_side_mismatch():
    # Local LONG but exchange has negative position (= SHORT).
    rep = reconcile(
        local_positions=[_local(side="LONG", qty="100")],
        exchange_positions=[_exch(amt="-100")],
    )
    assert not rep.is_clean
    assert rep.mismatches[0].kind == "side_mismatch"


def test_status_drift():
    rep = reconcile(
        local_positions=[_local(status="closing")],
        exchange_positions=[_exch()],
    )
    assert not rep.is_clean
    assert rep.mismatches[0].kind == "status_drift"


def test_qty_within_tolerance_is_clean():
    rep = reconcile(
        local_positions=[_local(qty="100")],
        exchange_positions=[_exch(amt="100.00000000005")],   # well within tolerance
    )
    assert rep.is_clean


def test_multi_position_partial_drift():
    locals_ = [_local(symbol="A"), _local(symbol="B"), _local(symbol="C")]
    exch = [_exch(symbol="A"), _exch(symbol="C", amt="50")]
    rep = reconcile(local_positions=locals_, exchange_positions=exch)
    kinds = sorted(m.kind for m in rep.mismatches)
    assert kinds == sorted(["missing_on_exchange", "qty_mismatch"])
    assert rep.matched == 1   # only A is clean
