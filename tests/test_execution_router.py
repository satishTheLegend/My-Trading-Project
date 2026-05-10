"""Execution router: mode routing, threshold logic, queue handling.

All mocked — uses fake LiveExecution + fake order book."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from scripts.execution_router import ExecutionOutcome, ExecutionRouter
from scripts.live_execution import OrderResult
from scripts.market_data import OrderBook, OrderBookLevel
from scripts.pending_approvals import PendingApprovalsStore
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


def _book(price: float = 0.07655) -> OrderBook:
    return OrderBook(
        symbol="DOGEUSDT", last_update_id=1,
        bids=(OrderBookLevel(price=Decimal("0.07650"), quantity=Decimal("100000")),),
        asks=(OrderBookLevel(price=Decimal(str(price)), quantity=Decimal("100000")),),
        transaction_time_ms=1,
    )


class _FakeLiveExecution:
    """Minimal stand-in for LiveExecution. Records every call."""
    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self.next_order_id = 1000

    def set_margin_mode(self, symbol, mode):
        self.calls.append({"set_margin_mode": (symbol, mode)})
        return {}

    def set_leverage(self, symbol, leverage):
        self.calls.append({"set_leverage": (symbol, leverage)})
        return {}

    def place_market_entry(self, spec, *, side, quantity, risk_approval_id, client_order_id=None):
        self.calls.append({
            "place_market_entry": {
                "symbol": spec.symbol, "side": side, "quantity": str(quantity),
                "risk_approval_id": risk_approval_id, "client_order_id": client_order_id,
            }
        })
        oid = self.next_order_id
        self.next_order_id += 1
        return OrderResult(
            success=True, order_id=oid, client_order_id=client_order_id,
            status="FILLED", symbol=spec.symbol,
            side="BUY" if side == "LONG" else "SELL",
            type="MARKET",
            avg_price=Decimal("0.07655"), executed_qty=quantity,
            cum_quote=Decimal("0.07655") * quantity,
            reduce_only=False, raw={},
        )


# ---------------------------------------------------------------------------
# PAPER mode
# ---------------------------------------------------------------------------


def test_paper_mode_fills_via_paper_execution(doge_spec, tmp_path):
    router = ExecutionRouter(
        live_execution=None,
        approvals_store=PendingApprovalsStore(tmp_path / "p.json"),
    )
    out = router.route(
        mode="PAPER_TRADING", proposal_id="P-1", spec=doge_spec, side="LONG",
        quantity=Decimal("100"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2.5"), estimated_fees_usdt=Decimal("0.01"),
        liquidation_price=None, strategy="pullback_long",
        order_book=_book(),
    )
    assert out.status == "paper_filled"
    assert out.paper_fill is not None
    assert out.average_price == Decimal("0.07655")


# ---------------------------------------------------------------------------
# SEMI_AUTO_LIVE: small notional auto-fires
# ---------------------------------------------------------------------------


def test_semi_auto_below_threshold_fires_live(doge_spec, tmp_path):
    fake = _FakeLiveExecution()
    store = PendingApprovalsStore(tmp_path / "p.json")
    router = ExecutionRouter(
        live_execution=fake, approvals_store=store,
    )
    # Mark first-trade flag so it doesn't trip the defensive rule.
    router._first_live_trade_done = True

    # Notional = 0.07655 * 100 = ~7.655 USDT, well below $50.
    out = router.route(
        mode="SEMI_AUTO_LIVE", proposal_id="P-2", spec=doge_spec, side="LONG",
        quantity=Decimal("100"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2.5"), estimated_fees_usdt=Decimal("0.01"),
        liquidation_price=None, strategy="pullback_long",
    )
    assert out.status == "filled"
    assert out.order_id == 1000
    # No queued entry should exist.
    assert store.load_pending() == []


def test_semi_auto_first_trade_always_queues(doge_spec, tmp_path):
    fake = _FakeLiveExecution()
    store = PendingApprovalsStore(tmp_path / "p.json")
    router = ExecutionRouter(live_execution=fake, approvals_store=store)
    # _first_live_trade_done is False by default → defensive rule fires.

    out = router.route(
        mode="SEMI_AUTO_LIVE", proposal_id="P-3", spec=doge_spec, side="LONG",
        quantity=Decimal("100"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2.5"), estimated_fees_usdt=Decimal("0.01"),
        liquidation_price=None, strategy="pullback_long",
    )
    assert out.status == "queued_for_approval"
    assert out.approval is not None
    assert "first_live_trade_of_session" in out.approval.triggered_rules
    queued = store.load_pending()
    assert len(queued) == 1


# ---------------------------------------------------------------------------
# SEMI_AUTO_LIVE: large notional always queues
# ---------------------------------------------------------------------------


def test_semi_auto_above_threshold_queues(doge_spec, tmp_path):
    fake = _FakeLiveExecution()
    store = PendingApprovalsStore(tmp_path / "p.json")
    router = ExecutionRouter(live_execution=fake, approvals_store=store)
    router._first_live_trade_done = True

    # Notional = 0.07655 * 1000 = ~76.55 USDT > $50.
    out = router.route(
        mode="SEMI_AUTO_LIVE", proposal_id="P-4", spec=doge_spec, side="LONG",
        quantity=Decimal("1000"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("25"), estimated_fees_usdt=Decimal("0.075"),
        liquidation_price=None, strategy="pullback_long",
    )
    assert out.status == "queued_for_approval"
    assert "notional_above_threshold" in out.approval.triggered_rules
    # No live order placed.
    assert all("place_market_entry" not in c for c in fake.calls)


# ---------------------------------------------------------------------------
# Approved-queue execution worker
# ---------------------------------------------------------------------------


def test_execute_approved_queue_fires_and_marks_executed(doge_spec, tmp_path):
    fake = _FakeLiveExecution()
    store = PendingApprovalsStore(tmp_path / "p.json")
    router = ExecutionRouter(live_execution=fake, approvals_store=store)
    router._first_live_trade_done = True

    # Queue a big trade.
    router.route(
        mode="SEMI_AUTO_LIVE", proposal_id="P-5", spec=doge_spec, side="LONG",
        quantity=Decimal("1000"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("25"), estimated_fees_usdt=Decimal("0.075"),
        liquidation_price=None, strategy="pullback_long",
    )
    pending = store.load_pending()
    assert len(pending) == 1
    # User approves it.
    store.transition(pending[0].approval_id, to="approved", notes="tested")
    # Worker picks it up.
    outs = router.execute_approved_queue(spec_lookup={"DOGEUSDT": doge_spec})
    assert len(outs) == 1
    assert outs[0].status == "filled"
    # Store reflects executed status.
    after = store.find(pending[0].approval_id)
    assert after.status == "executed"
    assert after.executed_order_id == 1000
    assert after.executed_avg_price == Decimal("0.07655")


def test_execute_approved_queue_skips_unknown_symbol(doge_spec, tmp_path):
    fake = _FakeLiveExecution()
    store = PendingApprovalsStore(tmp_path / "p.json")
    router = ExecutionRouter(live_execution=fake, approvals_store=store)
    router._first_live_trade_done = True
    router.route(
        mode="SEMI_AUTO_LIVE", proposal_id="P-6", spec=doge_spec, side="LONG",
        quantity=Decimal("1000"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("25"), estimated_fees_usdt=Decimal("0.075"),
        liquidation_price=None, strategy="pullback_long",
    )
    p = store.load_pending()[0]
    store.transition(p.approval_id, to="approved", notes="tested")
    # Worker called with EMPTY spec_lookup.
    outs = router.execute_approved_queue(spec_lookup={})
    assert outs[0].status == "rejected"
    after = store.find(p.approval_id)
    assert after.status == "rejected"


def test_paper_without_book_rejects_cleanly(doge_spec, tmp_path):
    router = ExecutionRouter(
        live_execution=None,
        approvals_store=PendingApprovalsStore(tmp_path / "p.json"),
    )
    out = router.route(
        mode="PAPER_TRADING", proposal_id="P-7", spec=doge_spec, side="LONG",
        quantity=Decimal("100"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2.5"), estimated_fees_usdt=Decimal("0.01"),
        liquidation_price=None, strategy="pullback_long",
        order_book=None,
    )
    assert out.status == "rejected"
    assert out.rejection_reason and "order_book" in out.rejection_reason
