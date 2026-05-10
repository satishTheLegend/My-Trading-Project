"""Live execution wrapper — Phase 4.

Mirrors the surface area of `paper_execution.py` but sends real signed
requests through `SignedClient`. This module is the **only** place in the
codebase that constructs an order payload destined for Binance.

Hard rules (mirrored to memory/safety-events.md when violated):
  1. Live execution is refused unless the user explicitly enabled live mode
     (see `agency/safety-rules.md`).
  2. Risk Manager approval ID must be provided to every order method.
  3. Exit functions ALWAYS pass `reduceOnly=true`. The class enforces this
     — there is no way to set `reduceOnly=false` from the exit helpers.
  4. Margin mode and leverage are set per-symbol BEFORE the entry order, in
     idempotent calls (Binance returns -4046 / -4059 if the value is already
     what we asked for, which we treat as success).
  5. Every successful order is journaled.

Why a separate file?
--------------------
Keeping paper and live in different modules means a paper-only test cycle
can't accidentally pick up a live execution call from a missing import. It
also makes "is this code path live?" easy to grep — if the file is named
`live_execution.py`, the answer is yes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .binance_signed_client import (
    SignedClient,
    SignedRequestsDisabledError,
)
from .symbol_filters import SymbolSpec, validate_order

log = logging.getLogger(__name__)


# Idempotent-success error codes from Binance — treated as no-ops, not failures.
#  -4046  "No need to change margin type." (already on the requested mode)
#  -4059  "No need to change leverage."   (already at the requested leverage)
IDEMPOTENT_OK_CODES = {-4046, -4059}


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderResult:
    success: bool
    order_id: int | None
    client_order_id: str | None
    status: str                  # 'NEW' | 'FILLED' | 'PARTIALLY_FILLED' | 'CANCELED' | 'REJECTED' | 'EXPIRED'
    symbol: str
    side: str
    type: str
    avg_price: Decimal
    executed_qty: Decimal
    cum_quote: Decimal           # quote-asset amount filled
    reduce_only: bool
    raw: dict[str, Any]
    error_code: int | None = None
    error_msg: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "status": self.status,
            "symbol": self.symbol,
            "side": self.side,
            "type": self.type,
            "avg_price": str(self.avg_price),
            "executed_qty": str(self.executed_qty),
            "cum_quote": str(self.cum_quote),
            "reduce_only": self.reduce_only,
            "error_code": self.error_code,
            "error_msg": self.error_msg,
        }


# ----------------------------------------------------------------------------
# Live execution
# ----------------------------------------------------------------------------


class LiveExecution:
    def __init__(
        self,
        client: SignedClient | None = None,
        *,
        require_explicit_live: bool = True,
    ) -> None:
        self.client = client or SignedClient()
        self._require_explicit = require_explicit_live

    # ----- preflight ---------------------------------------------------

    def _preflight(self) -> None:
        if not self.client.is_signed_enabled:
            raise SignedRequestsDisabledError(
                "live execution refused — Safety Agent has not opened the signed gate"
            )

    # ----- margin mode / leverage --------------------------------------

    def set_margin_mode(self, symbol: str, mode: str) -> dict[str, Any]:
        """``mode`` is "ISOLATED" or "CROSSED" (Binance's terminology — note CROSSED with -ED)."""
        self._preflight()
        if mode not in ("ISOLATED", "CROSSED"):
            raise ValueError("mode must be 'ISOLATED' or 'CROSSED'")
        try:
            return self.client.signed_request(
                "POST", "/fapi/v1/marginType",
                params={"symbol": symbol, "marginType": mode},
            )
        except Exception as e:
            code = getattr(e, "code", None)
            if code in IDEMPOTENT_OK_CODES:
                log.info("margin mode for %s already %s", symbol, mode)
                return {"code": code, "msg": "no-op"}
            raise

    def set_leverage(self, symbol: str, leverage: int) -> dict[str, Any]:
        self._preflight()
        if not 1 <= leverage <= 125:
            raise ValueError("leverage out of [1, 125]")
        try:
            return self.client.signed_request(
                "POST", "/fapi/v1/leverage",
                params={"symbol": symbol, "leverage": leverage},
            )
        except Exception as e:
            code = getattr(e, "code", None)
            if code in IDEMPOTENT_OK_CODES:
                log.info("leverage for %s already %dx", symbol, leverage)
                return {"code": code, "msg": "no-op"}
            raise

    # ----- entries -----------------------------------------------------

    def place_market_entry(
        self,
        spec: SymbolSpec,
        *,
        side: str,
        quantity: Decimal,
        risk_approval_id: str,
        client_order_id: str | None = None,
    ) -> OrderResult:
        """MARKET entry order. Validates against symbol filters first."""
        self._preflight()
        if side not in ("LONG", "SHORT"):
            raise ValueError("side must be LONG or SHORT")
        if not risk_approval_id:
            raise ValueError("risk_approval_id is mandatory for live entries")

        binance_side = "BUY" if side == "LONG" else "SELL"
        v = validate_order(spec, price=None, quantity=quantity, is_market=True)
        if not v.ok:
            return _failure_result(spec.symbol, binance_side, "MARKET",
                                   reduce_only=False,
                                   error_msg=f"filter validation failed: {v.violations}")

        params: dict[str, Any] = {
            "symbol": spec.symbol,
            "side": binance_side,
            "type": "MARKET",
            "quantity": _fmt(quantity),
            "newClientOrderId": client_order_id or risk_approval_id[:36],
        }
        return _to_result(self.client.signed_request("POST", "/fapi/v1/order", params=params))

    def place_limit_entry(
        self,
        spec: SymbolSpec,
        *,
        side: str,
        quantity: Decimal,
        price: Decimal,
        risk_approval_id: str,
        time_in_force: str = "GTC",
        post_only: bool = False,
        client_order_id: str | None = None,
    ) -> OrderResult:
        self._preflight()
        if side not in ("LONG", "SHORT"):
            raise ValueError("side must be LONG or SHORT")
        if not risk_approval_id:
            raise ValueError("risk_approval_id is mandatory for live entries")
        if time_in_force not in ("GTC", "IOC", "FOK", "GTX"):
            raise ValueError("invalid timeInForce")

        binance_side = "BUY" if side == "LONG" else "SELL"
        v = validate_order(spec, price=price, quantity=quantity, is_market=False)
        if not v.ok:
            return _failure_result(spec.symbol, binance_side, "LIMIT",
                                   reduce_only=False,
                                   error_msg=f"filter validation failed: {v.violations}")

        params: dict[str, Any] = {
            "symbol": spec.symbol,
            "side": binance_side,
            "type": "LIMIT",
            "quantity": _fmt(quantity),
            "price": _fmt(price),
            "timeInForce": "GTX" if post_only else time_in_force,
            "newClientOrderId": client_order_id or risk_approval_id[:36],
        }
        return _to_result(self.client.signed_request("POST", "/fapi/v1/order", params=params))

    # ----- protective orders (always reduce-only) ----------------------

    def place_stop_market(
        self,
        spec: SymbolSpec,
        *,
        side: str,                    # the EXIT side: SELL for closing a LONG, BUY for closing a SHORT
        stop_price: Decimal,
        quantity: Decimal | None = None,
        close_position: bool = False,
        client_order_id: str | None = None,
    ) -> OrderResult:
        self._preflight()
        return self._reduce_only_protective(
            spec, side=side, type_="STOP_MARKET",
            stop_price=stop_price, price=None, quantity=quantity,
            close_position=close_position, client_order_id=client_order_id,
        )

    def place_take_profit_market(
        self,
        spec: SymbolSpec,
        *,
        side: str,
        stop_price: Decimal,
        quantity: Decimal | None = None,
        close_position: bool = False,
        client_order_id: str | None = None,
    ) -> OrderResult:
        self._preflight()
        return self._reduce_only_protective(
            spec, side=side, type_="TAKE_PROFIT_MARKET",
            stop_price=stop_price, price=None, quantity=quantity,
            close_position=close_position, client_order_id=client_order_id,
        )

    def close_position_market(
        self,
        spec: SymbolSpec,
        *,
        position_side: str,           # "LONG" or "SHORT" — the side of the OPEN position
        quantity: Decimal,
        client_order_id: str | None = None,
    ) -> OrderResult:
        """Reduce-only market exit. Use this for partial / full / emergency exits."""
        self._preflight()
        if position_side not in ("LONG", "SHORT"):
            raise ValueError("position_side must be LONG or SHORT")
        binance_side = "SELL" if position_side == "LONG" else "BUY"
        params: dict[str, Any] = {
            "symbol": spec.symbol,
            "side": binance_side,
            "type": "MARKET",
            "quantity": _fmt(quantity),
            "reduceOnly": True,
        }
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        return _to_result(self.client.signed_request("POST", "/fapi/v1/order", params=params))

    def _reduce_only_protective(
        self,
        spec: SymbolSpec,
        *,
        side: str,
        type_: str,
        stop_price: Decimal,
        price: Decimal | None,
        quantity: Decimal | None,
        close_position: bool,
        client_order_id: str | None,
    ) -> OrderResult:
        if side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL (the EXIT side)")
        if not close_position and quantity is None:
            raise ValueError("either close_position=True or quantity must be set")
        params: dict[str, Any] = {
            "symbol": spec.symbol,
            "side": side,
            "type": type_,
            "stopPrice": _fmt(stop_price),
            "reduceOnly": True,           # NON-NEGOTIABLE for protective orders
        }
        if close_position:
            params["closePosition"] = True
        else:
            params["quantity"] = _fmt(quantity)
        if price is not None:
            params["price"] = _fmt(price)
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        return _to_result(self.client.signed_request("POST", "/fapi/v1/order", params=params))

    # ----- queries / cancels -------------------------------------------

    def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        self._preflight()
        params = {"symbol": symbol} if symbol else None
        return list(self.client.signed_request("GET", "/fapi/v1/openOrders", params=params))

    def cancel_order(self, symbol: str, order_id: int | None = None,
                     client_order_id: str | None = None) -> dict[str, Any]:
        self._preflight()
        if order_id is None and client_order_id is None:
            raise ValueError("must pass order_id or client_order_id")
        params: dict[str, Any] = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if client_order_id is not None:
            params["origClientOrderId"] = client_order_id
        return self.client.signed_request("DELETE", "/fapi/v1/order", params=params)

    def cancel_all_orders(self, symbol: str) -> dict[str, Any]:
        self._preflight()
        return self.client.signed_request(
            "DELETE", "/fapi/v1/allOpenOrders", params={"symbol": symbol},
        )


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _fmt(d: Decimal | int | float) -> str:
    """Format a Decimal for Binance — use the canonical decimal string, never scientific notation."""
    if isinstance(d, Decimal):
        # ``format(d, 'f')`` avoids scientific notation for very small/large values.
        s = format(d, "f")
        return s
    return str(d)


def _to_result(raw: dict[str, Any]) -> OrderResult:
    return OrderResult(
        success=True,
        order_id=int(raw.get("orderId", 0)) or None,
        client_order_id=raw.get("clientOrderId"),
        status=str(raw.get("status", "")),
        symbol=str(raw.get("symbol", "")),
        side=str(raw.get("side", "")),
        type=str(raw.get("type", "")),
        avg_price=Decimal(str(raw.get("avgPrice", "0") or "0")),
        executed_qty=Decimal(str(raw.get("executedQty", "0") or "0")),
        cum_quote=Decimal(str(raw.get("cumQuote", "0") or "0")),
        reduce_only=bool(raw.get("reduceOnly", False)),
        raw=raw,
    )


def _failure_result(symbol: str, side: str, type_: str, *, reduce_only: bool, error_msg: str) -> OrderResult:
    return OrderResult(
        success=False, order_id=None, client_order_id=None,
        status="REJECTED", symbol=symbol, side=side, type=type_,
        avg_price=Decimal("0"), executed_qty=Decimal("0"), cum_quote=Decimal("0"),
        reduce_only=reduce_only, raw={}, error_code=None, error_msg=error_msg,
    )


__all__ = [
    "OrderResult",
    "LiveExecution",
    "IDEMPOTENT_OK_CODES",
]
