"""Live execution: order construction, reduce-only enforcement, idempotent
margin/leverage handling. All mocked — no real HTTP."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from scripts.binance_signed_client import (
    BinanceAPIError,
    SignedClient,
    SignedRequestsDisabledError,
)
from scripts.live_execution import (
    IDEMPOTENT_OK_CODES,
    LiveExecution,
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


def _client_with_capture(monkeypatch) -> tuple[SignedClient, dict[str, Any]]:
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_API_SECRET", "s")
    monkeypatch.delenv("BINANCE_LIVE", raising=False)
    captured: dict[str, Any] = {"calls": []}

    def fake_signed(self, method, path, params=None):
        captured["calls"].append({"method": method, "path": path, "params": params})
        # Return shape that LiveExecution._to_result expects.
        if path == "/fapi/v1/order":
            return {
                "orderId": 1234, "clientOrderId": (params or {}).get("newClientOrderId", "cid"),
                "status": "NEW", "symbol": (params or {}).get("symbol", ""),
                "side": (params or {}).get("side", ""),
                "type": (params or {}).get("type", ""),
                "avgPrice": "0", "executedQty": "0", "cumQuote": "0",
                "reduceOnly": (params or {}).get("reduceOnly", False),
            }
        return {}

    monkeypatch.setattr(SignedClient, "signed_request", fake_signed)

    client = SignedClient()
    client.enable_signed_requests()
    return client, captured


# ---------------------------------------------------------------------------
# Preflight gating
# ---------------------------------------------------------------------------


def test_live_execution_refused_until_gate_open(monkeypatch, doge_spec):
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_API_SECRET", "s")
    client = SignedClient()      # gate not opened
    ex = LiveExecution(client)
    with pytest.raises(SignedRequestsDisabledError):
        ex.place_market_entry(
            doge_spec, side="LONG", quantity=Decimal("100"),
            risk_approval_id="APPROVE-1",
        )


# ---------------------------------------------------------------------------
# Margin mode + leverage
# ---------------------------------------------------------------------------


def test_set_margin_mode_idempotent_on_no_change(monkeypatch, doge_spec):
    client, captured = _client_with_capture(monkeypatch)

    def fake_signed(self, method, path, params=None):
        captured["calls"].append({"method": method, "path": path, "params": params})
        # Simulate Binance returning -4046 (already on requested margin type).
        raise BinanceAPIError(400, -4046, "No need to change margin type.", "<redacted>")

    monkeypatch.setattr(SignedClient, "signed_request", fake_signed)
    ex = LiveExecution(client)
    out = ex.set_margin_mode("DOGEUSDT", "ISOLATED")
    assert out == {"code": -4046, "msg": "no-op"}


def test_set_leverage_validates_range(monkeypatch, doge_spec):
    client, _ = _client_with_capture(monkeypatch)
    ex = LiveExecution(client)
    with pytest.raises(ValueError):
        ex.set_leverage("DOGEUSDT", 0)
    with pytest.raises(ValueError):
        ex.set_leverage("DOGEUSDT", 200)


# ---------------------------------------------------------------------------
# Entry orders
# ---------------------------------------------------------------------------


def test_market_entry_long_constructs_buy(monkeypatch, doge_spec):
    client, captured = _client_with_capture(monkeypatch)
    ex = LiveExecution(client)
    result = ex.place_market_entry(
        doge_spec, side="LONG", quantity=Decimal("100"),
        risk_approval_id="APPROVE-1",
    )
    assert result.success
    call = captured["calls"][-1]
    assert call["path"] == "/fapi/v1/order"
    assert call["params"]["side"] == "BUY"
    assert call["params"]["type"] == "MARKET"
    assert call["params"]["quantity"] == "100"


def test_market_entry_short_constructs_sell(monkeypatch, doge_spec):
    client, captured = _client_with_capture(monkeypatch)
    ex = LiveExecution(client)
    ex.place_market_entry(
        doge_spec, side="SHORT", quantity=Decimal("100"),
        risk_approval_id="APPROVE-2",
    )
    assert captured["calls"][-1]["params"]["side"] == "SELL"


def test_entry_rejects_invalid_filters(monkeypatch, doge_spec):
    client, _ = _client_with_capture(monkeypatch)
    ex = LiveExecution(client)
    # qty 0.5 violates LOT_SIZE step=1.
    result = ex.place_market_entry(
        doge_spec, side="LONG", quantity=Decimal("0.5"),
        risk_approval_id="APPROVE-3",
    )
    assert not result.success
    assert "filter validation failed" in (result.error_msg or "")


def test_entry_requires_risk_approval_id(monkeypatch, doge_spec):
    client, _ = _client_with_capture(monkeypatch)
    ex = LiveExecution(client)
    with pytest.raises(ValueError):
        ex.place_market_entry(doge_spec, side="LONG", quantity=Decimal("100"),
                              risk_approval_id="")


# ---------------------------------------------------------------------------
# Reduce-only enforcement
# ---------------------------------------------------------------------------


def test_close_position_market_always_reduce_only(monkeypatch, doge_spec):
    client, captured = _client_with_capture(monkeypatch)
    ex = LiveExecution(client)
    ex.close_position_market(doge_spec, position_side="LONG", quantity=Decimal("50"))
    params = captured["calls"][-1]["params"]
    assert params["reduceOnly"] is True
    assert params["side"] == "SELL"               # exiting a LONG
    assert params["quantity"] == "50"


def test_close_position_short_emits_buy(monkeypatch, doge_spec):
    client, captured = _client_with_capture(monkeypatch)
    ex = LiveExecution(client)
    ex.close_position_market(doge_spec, position_side="SHORT", quantity=Decimal("50"))
    assert captured["calls"][-1]["params"]["side"] == "BUY"
    assert captured["calls"][-1]["params"]["reduceOnly"] is True


def test_stop_market_is_reduce_only_with_close_position_flag(monkeypatch, doge_spec):
    client, captured = _client_with_capture(monkeypatch)
    ex = LiveExecution(client)
    ex.place_stop_market(
        doge_spec, side="SELL", stop_price=Decimal("0.07500"),
        close_position=True,
    )
    params = captured["calls"][-1]["params"]
    assert params["type"] == "STOP_MARKET"
    assert params["reduceOnly"] is True
    assert params["closePosition"] is True
    assert params["stopPrice"] == "0.07500"


def test_take_profit_market_is_reduce_only(monkeypatch, doge_spec):
    client, captured = _client_with_capture(monkeypatch)
    ex = LiveExecution(client)
    ex.place_take_profit_market(
        doge_spec, side="SELL", stop_price=Decimal("0.07900"),
        quantity=Decimal("50"),
    )
    params = captured["calls"][-1]["params"]
    assert params["type"] == "TAKE_PROFIT_MARKET"
    assert params["reduceOnly"] is True
    assert "closePosition" not in params      # only set when explicitly requested
    assert params["quantity"] == "50"


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


def test_cancel_order_requires_id_or_client_id(monkeypatch, doge_spec):
    client, _ = _client_with_capture(monkeypatch)
    ex = LiveExecution(client)
    with pytest.raises(ValueError):
        ex.cancel_order("DOGEUSDT")


# ---------------------------------------------------------------------------
# Algo-order helpers (post-2025-12 schema: algoType / triggerPrice / clientAlgoId)
# ---------------------------------------------------------------------------


def _algo_client(monkeypatch) -> tuple[SignedClient, dict[str, Any]]:
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_API_SECRET", "s")
    monkeypatch.delenv("BINANCE_LIVE", raising=False)
    captured: dict[str, Any] = {"calls": []}

    def fake_signed(self, method, path, params=None):
        captured["calls"].append({"method": method, "path": path, "params": params})
        if path == "/fapi/v1/algoOrder":
            return {
                "algoId": 3000001506000001,
                "clientAlgoId": (params or {}).get("clientAlgoId", "cid"),
                "algoStatus": "NEW",
                "symbol": (params or {}).get("symbol", ""),
                "side": (params or {}).get("side", ""),
                "orderType": (params or {}).get("orderType", ""),
                "reduceOnly": True,
            }
        return {}

    monkeypatch.setattr(SignedClient, "signed_request", fake_signed)
    client = SignedClient()
    client.enable_signed_requests()
    return client, captured


def test_place_algo_stop_market_uses_new_schema(monkeypatch, doge_spec):
    client, captured = _algo_client(monkeypatch)
    ex = LiveExecution(client)
    result = ex.place_algo_stop_market(
        doge_spec, side="SELL", stop_price=Decimal("0.07500"),
        quantity=Decimal("100"), client_order_id="SL-PROP-1",
    )
    assert result.success
    call = captured["calls"][-1]
    assert call["method"] == "POST"
    assert call["path"] == "/fapi/v1/algoOrder"
    params = call["params"]
    # New-schema mandatory fields:
    assert params["algoType"] == "CONDITIONAL"
    assert params["type"] == "STOP_MARKET"
    assert params["triggerPrice"] == "0.07500"
    assert params["clientAlgoId"] == "SL-PROP-1"
    assert params["positionSide"] == "BOTH"
    assert params["timeInForce"] == "GTC"
    assert params["workingType"] == "MARK_PRICE"
    assert params["reduceOnly"] == "true"
    assert params["priceProtect"] == "true"
    # Legacy fields MUST NOT be sent.
    assert "stopPrice" not in params
    assert "newClientOrderId" not in params
    # Result must carry the algoId as order_id.
    assert result.order_id == 3000001506000001
    assert result.client_order_id == "SL-PROP-1"


def test_place_algo_take_profit_market_uses_new_schema(monkeypatch, doge_spec):
    client, captured = _algo_client(monkeypatch)
    ex = LiveExecution(client)
    result = ex.place_algo_take_profit_market(
        doge_spec, side="SELL", stop_price=Decimal("0.07900"),
        quantity=Decimal("100"), client_order_id="TP-PROP-1",
    )
    assert result.success
    params = captured["calls"][-1]["params"]
    assert params["algoType"] == "CONDITIONAL"
    assert params["type"] == "TAKE_PROFIT_MARKET"
    assert params["triggerPrice"] == "0.07900"
    assert params["clientAlgoId"] == "TP-PROP-1"
    assert "stopPrice" not in params
    assert "newClientOrderId" not in params


def test_cancel_algo_order_uses_algo_id_param(monkeypatch, doge_spec):
    client, captured = _algo_client(monkeypatch)
    ex = LiveExecution(client)
    ex.cancel_algo_order("DOGEUSDT", algo_id=3000001506000001)
    call = captured["calls"][-1]
    assert call["method"] == "DELETE"
    assert call["path"] == "/fapi/v1/algoOrder"
    assert call["params"]["symbol"] == "DOGEUSDT"
    assert call["params"]["algoId"] == "3000001506000001"
