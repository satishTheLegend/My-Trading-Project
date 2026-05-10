"""Emergency close: happy path + verify-residual + per-symbol error isolation.
All mocked — no live calls."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from scripts.account import Account, ExchangePosition
from scripts.binance_signed_client import SignedClient
from scripts.emergency_close import emergency_close_all
from scripts.live_execution import LiveExecution, OrderResult
from scripts.symbol_filters import parse_symbol_spec


def _spec(symbol: str = "DOGEUSDT"):
    raw = {
        "symbol": symbol, "pair": symbol, "contractType": "PERPETUAL",
        "status": "TRADING", "baseAsset": symbol[:-4], "quoteAsset": "USDT",
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


def _exch(symbol: str, amt: str) -> ExchangePosition:
    return ExchangePosition(
        symbol=symbol, position_amt=Decimal(amt),
        entry_price=Decimal("0.07654"), mark_price=Decimal("0.07700"),
        un_realized_profit=Decimal("0"),
        leverage=3, margin_type="isolated",
        isolated_wallet=Decimal("2"),
        liquidation_price=Decimal("0.05100"),
        update_time_ms=0,
    )


class _FakeAccount:
    def __init__(self, positions_sequence: list[list[ExchangePosition]]):
        self._sequence = positions_sequence
        self._idx = 0

    def get_open_positions(self, symbol: str | None = None):
        positions = self._sequence[self._idx]
        if self._idx < len(self._sequence) - 1:
            self._idx += 1
        return positions


class _FakeExecution:
    def __init__(self, fail_symbols: set[str] | None = None):
        self.calls: list[dict[str, Any]] = []
        self.fail_symbols = fail_symbols or set()

    def close_position_market(self, spec, *, position_side: str, quantity: Decimal,
                              client_order_id: str | None = None) -> OrderResult:
        self.calls.append({
            "symbol": spec.symbol, "side": position_side,
            "qty": quantity, "client_order_id": client_order_id,
        })
        if spec.symbol in self.fail_symbols:
            raise RuntimeError("simulated close failure")
        return OrderResult(
            success=True, order_id=42, client_order_id=client_order_id,
            status="FILLED", symbol=spec.symbol,
            side="SELL" if position_side == "LONG" else "BUY",
            type="MARKET",
            avg_price=Decimal("0.07700"),
            executed_qty=quantity,
            cum_quote=Decimal("0.07700") * quantity,
            reduce_only=True, raw={},
        )


def test_no_open_positions_is_noop_success():
    account = _FakeAccount([[]])
    execution = _FakeExecution()
    spec_map = {"DOGEUSDT": _spec()}
    report = emergency_close_all(account=account, execution=execution, spec_map=spec_map)
    assert report.success
    assert report.initial_open_positions == 0
    assert report.attempts == ()


def test_closes_every_open_position_and_verifies_flat():
    initial = [_exch("DOGEUSDT", "100"), _exch("SHIBUSDT", "-200")]
    after = []   # all flat
    account = _FakeAccount([initial, after])
    execution = _FakeExecution()
    spec_map = {"DOGEUSDT": _spec("DOGEUSDT"), "SHIBUSDT": _spec("SHIBUSDT")}

    report = emergency_close_all(account=account, execution=execution, spec_map=spec_map)
    assert report.success
    assert report.initial_open_positions == 2
    assert report.residual_open_positions == 0
    assert len(report.attempts) == 2
    # Long DOGE → close with SELL, short SHIB → close with BUY
    sides = {a.symbol: a.order_result.side for a in report.attempts}
    assert sides["DOGEUSDT"] == "SELL"
    assert sides["SHIBUSDT"] == "BUY"


def test_per_symbol_error_isolated_other_closures_proceed():
    initial = [_exch("DOGEUSDT", "100"), _exch("SHIBUSDT", "-200")]
    after = [_exch("DOGEUSDT", "100")]    # DOGE failed to close
    account = _FakeAccount([initial, after])
    execution = _FakeExecution(fail_symbols={"DOGEUSDT"})
    spec_map = {"DOGEUSDT": _spec("DOGEUSDT"), "SHIBUSDT": _spec("SHIBUSDT")}

    report = emergency_close_all(account=account, execution=execution, spec_map=spec_map)
    assert not report.success
    assert report.residual_open_positions == 1
    # SHIB still got its close attempt despite DOGE failing.
    by_symbol = {a.symbol: a for a in report.attempts}
    assert by_symbol["DOGEUSDT"].error is not None
    assert by_symbol["SHIBUSDT"].error is None


def test_unknown_symbol_in_spec_map_skipped_with_error():
    initial = [_exch("MYSTERYUSDT", "100")]
    after = [_exch("MYSTERYUSDT", "100")]
    account = _FakeAccount([initial, after])
    execution = _FakeExecution()
    spec_map = {}  # symbol not in map

    report = emergency_close_all(account=account, execution=execution, spec_map=spec_map)
    assert not report.success
    assert report.attempts[0].error and "exchangeInfo" in report.attempts[0].error
