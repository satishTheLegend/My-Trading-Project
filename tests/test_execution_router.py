"""Execution router: mode routing, threshold logic, queue handling.

All mocked — uses fake LiveExecution + fake order book."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from scripts.execution_router import (
    ExecutionOutcome,
    ExecutionRouter,
    _build_algo_client_id,
)
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
    """Minimal stand-in for LiveExecution. Records every call.

    Bracket placement helpers default to success; tests that want to exercise
    the naked-rescue path set ``fail_sl=True`` or ``fail_tp=True`` on the
    instance.
    """
    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self.next_order_id = 1000
        self.next_algo_id = 90000
        self.fail_sl: bool = False
        self.fail_tp: bool = False
        self.fail_close: bool = False

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

    def _algo_result(self, *, spec, side, type_, stop_price, quantity, client_order_id, success):
        aid = self.next_algo_id
        self.next_algo_id += 1
        return OrderResult(
            success=success,
            order_id=aid if success else None,
            client_order_id=client_order_id,
            status="NEW" if success else "REJECTED",
            symbol=spec.symbol, side=side, type=type_,
            avg_price=Decimal("0"), executed_qty=Decimal("0"),
            cum_quote=Decimal("0"),
            reduce_only=True, raw={"algoId": aid} if success else {},
            error_code=None if success else -2021,
            error_msg=None if success else "simulated bracket failure",
        )

    def place_algo_stop_market(self, spec, *, side, stop_price, quantity,
                               working_type="MARK_PRICE", price_protect=True,
                               client_order_id=None):
        self.calls.append({
            "place_algo_stop_market": {
                "symbol": spec.symbol, "side": side, "stop_price": str(stop_price),
                "quantity": str(quantity), "client_order_id": client_order_id,
            }
        })
        return self._algo_result(
            spec=spec, side=side, type_="STOP_MARKET",
            stop_price=stop_price, quantity=quantity,
            client_order_id=client_order_id, success=not self.fail_sl,
        )

    def place_algo_take_profit_market(self, spec, *, side, stop_price, quantity,
                                      working_type="MARK_PRICE", price_protect=True,
                                      client_order_id=None):
        self.calls.append({
            "place_algo_take_profit_market": {
                "symbol": spec.symbol, "side": side, "stop_price": str(stop_price),
                "quantity": str(quantity), "client_order_id": client_order_id,
            }
        })
        return self._algo_result(
            spec=spec, side=side, type_="TAKE_PROFIT_MARKET",
            stop_price=stop_price, quantity=quantity,
            client_order_id=client_order_id, success=not self.fail_tp,
        )

    def cancel_algo_order(self, symbol, *, algo_id):
        self.calls.append({"cancel_algo_order": {"symbol": symbol, "algo_id": algo_id}})
        return {"algoId": algo_id, "status": "CANCELED"}

    def close_position_market(self, spec, *, position_side, quantity, client_order_id=None):
        self.calls.append({
            "close_position_market": {
                "symbol": spec.symbol, "position_side": position_side,
                "quantity": str(quantity), "client_order_id": client_order_id,
            }
        })
        oid = self.next_order_id
        self.next_order_id += 1
        if self.fail_close:
            return OrderResult(
                success=False, order_id=None, client_order_id=client_order_id,
                status="REJECTED", symbol=spec.symbol,
                side="SELL" if position_side == "LONG" else "BUY",
                type="MARKET",
                avg_price=Decimal("0"), executed_qty=Decimal("0"),
                cum_quote=Decimal("0"), reduce_only=True, raw={},
                error_code=-2022, error_msg="simulated close failure",
            )
        return OrderResult(
            success=True, order_id=oid, client_order_id=client_order_id,
            status="FILLED", symbol=spec.symbol,
            side="SELL" if position_side == "LONG" else "BUY",
            type="MARKET",
            avg_price=Decimal("0.07655"), executed_qty=quantity,
            cum_quote=Decimal("0.07655") * quantity,
            reduce_only=True, raw={},
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
    # Brackets must be placed and the algoIds embedded on the outcome.
    assert "sl" in out.algo_order_ids and "tp" in out.algo_order_ids
    assert out.algo_order_ids["sl"] and out.algo_order_ids["tp"]
    # Both bracket helpers must have been called.
    assert any("place_algo_stop_market" in c for c in fake.calls)
    assert any("place_algo_take_profit_market" in c for c in fake.calls)
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


# ---------------------------------------------------------------------------
# Naked-rescue: bracket placement failures MUST reduce-only close + pause safety
# ---------------------------------------------------------------------------


class _FakeSafety:
    """Tiny stand-in for SafetyStateManager.pause()."""
    def __init__(self):
        self.paused: list[dict[str, Any]] = []

    def pause(self, reason, *, carry_over_rollover=False, until_minutes=None):
        self.paused.append({
            "reason": reason, "carry_over_rollover": carry_over_rollover,
            "until_minutes": until_minutes,
        })
        return None


def test_full_auto_entry_with_sl_failure_triggers_reduce_only_close(doge_spec, tmp_path, monkeypatch):
    """Entry fills, SL placement fails → router must close the entry,
    pause safety, and return naked_rescued (NOT filled)."""
    fake = _FakeLiveExecution()
    fake.fail_sl = True
    safety = _FakeSafety()
    # Prevent journal_writer from touching memory/safety-events.md in test runs.
    monkeypatch.setattr(
        "scripts.execution_router.append_safety_event", lambda entry: None,
    )

    store = PendingApprovalsStore(tmp_path / "p.json")
    router = ExecutionRouter(
        live_execution=fake, approvals_store=store, safety=safety,
    )
    router._first_live_trade_done = True

    out = router.route(
        mode="FULL_AUTO_LIVE", proposal_id="P-NAKED-SL",
        spec=doge_spec, side="LONG",
        quantity=Decimal("100"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2.5"), estimated_fees_usdt=Decimal("0.01"),
        liquidation_price=None, strategy="pullback_long",
    )
    assert out.status == "naked_rescued"
    assert out.algo_order_ids == {}
    assert out.rejection_reason and "SL placement failed" in out.rejection_reason
    # Reduce-only close MUST have been issued.
    assert any("close_position_market" in c for c in fake.calls)
    # Safety MUST have been paused.
    assert len(safety.paused) == 1
    assert "naked_entry_rescue" in safety.paused[0]["reason"]
    assert safety.paused[0]["carry_over_rollover"] is True


def test_full_auto_entry_with_tp_failure_triggers_reduce_only_close(doge_spec, tmp_path, monkeypatch):
    """Entry fills + SL succeeds + TP fails → router must cancel the SL,
    close the entry, pause safety, return naked_rescued."""
    fake = _FakeLiveExecution()
    fake.fail_tp = True
    safety = _FakeSafety()
    monkeypatch.setattr(
        "scripts.execution_router.append_safety_event", lambda entry: None,
    )

    store = PendingApprovalsStore(tmp_path / "p.json")
    router = ExecutionRouter(
        live_execution=fake, approvals_store=store, safety=safety,
    )
    router._first_live_trade_done = True

    out = router.route(
        mode="FULL_AUTO_LIVE", proposal_id="P-NAKED-TP",
        spec=doge_spec, side="LONG",
        quantity=Decimal("100"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2.5"), estimated_fees_usdt=Decimal("0.01"),
        liquidation_price=None, strategy="pullback_long",
    )
    assert out.status == "naked_rescued"
    assert out.algo_order_ids == {}
    assert out.rejection_reason and "TP placement failed" in out.rejection_reason
    # SL was placed first and succeeded → must be cancelled during rescue.
    assert any("cancel_algo_order" in c for c in fake.calls)
    # Reduce-only close MUST have been issued.
    assert any("close_position_market" in c for c in fake.calls)
    # Safety MUST have been paused.
    assert len(safety.paused) == 1


def test_full_auto_entry_with_both_brackets_success_naked_window_zero(doge_spec, tmp_path):
    """Happy-path: entry + SL + TP all succeed atomically. Naked window = 0.

    Asserts the SL placement immediately follows the entry placement with no
    intervening foreign calls (other than margin/leverage setup).
    """
    fake = _FakeLiveExecution()
    safety = _FakeSafety()
    store = PendingApprovalsStore(tmp_path / "p.json")
    router = ExecutionRouter(
        live_execution=fake, approvals_store=store, safety=safety,
    )
    router._first_live_trade_done = True

    out = router.route(
        mode="FULL_AUTO_LIVE", proposal_id="P-CLEAN",
        spec=doge_spec, side="LONG",
        quantity=Decimal("100"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[Decimal("0.07800")],
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2.5"), estimated_fees_usdt=Decimal("0.01"),
        liquidation_price=None, strategy="pullback_long",
    )
    assert out.status == "filled"
    assert out.algo_order_ids["sl"]
    assert out.algo_order_ids["tp"]
    # Safety was NOT paused — clean fill.
    assert safety.paused == []
    # No reduce-only close was issued.
    assert all("close_position_market" not in c for c in fake.calls)
    # SL placement must come immediately after the entry placement (the only
    # thing allowed in between is margin/leverage setup). Compute the indices.
    entry_idx = next(i for i, c in enumerate(fake.calls) if "place_market_entry" in c)
    sl_idx = next(i for i, c in enumerate(fake.calls) if "place_algo_stop_market" in c)
    tp_idx = next(i for i, c in enumerate(fake.calls) if "place_algo_take_profit_market" in c)
    assert sl_idx > entry_idx
    assert tp_idx > sl_idx
    # Nothing weird between entry and SL — no foreign order calls.
    between = fake.calls[entry_idx + 1: sl_idx]
    assert all(
        "place_market_entry" not in c and "close_position_market" not in c
        for c in between
    )


def test_full_auto_entry_missing_sl_input_triggers_rescue(doge_spec, tmp_path, monkeypatch):
    """If caller forgets to supply stop_loss or TP targets, router must
    rescue the entry rather than persist a naked position."""
    fake = _FakeLiveExecution()
    safety = _FakeSafety()
    monkeypatch.setattr(
        "scripts.execution_router.append_safety_event", lambda entry: None,
    )

    store = PendingApprovalsStore(tmp_path / "p.json")
    router = ExecutionRouter(
        live_execution=fake, approvals_store=store, safety=safety,
    )
    router._first_live_trade_done = True

    out = router.route(
        mode="FULL_AUTO_LIVE", proposal_id="P-NOBRACKETS",
        spec=doge_spec, side="LONG",
        quantity=Decimal("100"), entry_price=Decimal("0.07655"),
        stop_loss=Decimal("0.07500"),
        take_profit_targets=[],          # <-- empty bracket spec
        leverage=3, margin_mode="ISOLATED",
        margin_usdt=Decimal("2.5"), estimated_fees_usdt=Decimal("0.01"),
        liquidation_price=None, strategy="pullback_long",
    )
    assert out.status == "naked_rescued"
    assert any("close_position_market" in c for c in fake.calls)
    assert len(safety.paused) == 1


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


# ---------------------------------------------------------------------------
# ERROR-20260511-8: clientAlgoId uniqueness on retries
# ---------------------------------------------------------------------------


def test_build_algo_client_id_back_to_back_calls_differ():
    """Two builds for the same role+proposal must differ across millisecond
    boundaries. We force the boundary with a tiny sleep so the test is not
    racy on fast machines."""
    import time as _t
    a = _build_algo_client_id("SL", "PROP-20260511-BILL-001")
    _t.sleep(0.002)  # cross at least one millisecond boundary
    b = _build_algo_client_id("SL", "PROP-20260511-BILL-001")
    assert a != b
    assert a.startswith("SL-PROP-20260511-BILL-001-")
    assert b.startswith("SL-PROP-20260511-BILL-001-")


def test_build_algo_client_id_respects_binance_36_char_limit():
    # Realistic same-day retry pattern from the BILL incident.
    sl_id = _build_algo_client_id("SL", "PROP-20260511-BILLUSDT-001")
    tp_id = _build_algo_client_id("TP", "PROP-20260511-BILLUSDT-001")
    assert len(sl_id) <= 36
    assert len(tp_id) <= 36
    # Pathological long proposal_id still fits.
    long_id = _build_algo_client_id("TP", "X" * 200)
    assert len(long_id) <= 36
    # Suffix (last 6 chars) must be preserved even under truncation —
    # that's what makes the id unique on retries.
    assert long_id[-6:].isdigit()
    # Role prefix preserved.
    assert long_id.startswith("TP-")
