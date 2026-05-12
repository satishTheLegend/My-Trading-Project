"""Binance USDT-M Futures symbol-filter helpers.

Every order Binance accepts must pass:
  - PRICE_FILTER     (price must be >= minPrice, <= maxPrice, multiple of tickSize)
  - LOT_SIZE         (qty must be >= minQty, <= maxQty, multiple of stepSize)
  - MARKET_LOT_SIZE  (same idea but only for market orders, sometimes stricter)
  - MIN_NOTIONAL     (price * qty >= notional, USDT)
  - PERCENT_PRICE    (limit price within +/- multiplierUp/multiplierDown vs mark)

If we send a quantity that violates any filter, Binance rejects with -4014, -1111,
-4131, etc. The position-sizing agent calls into here BEFORE building an
execution plan, so violations are caught in code rather than as exchange errors.

This module is deliberately decimal-correct: it uses ``decimal.Decimal`` end-to-end
because float division on small-cap decimal-priced tokens (e.g. 0.00001234) loses
precision quickly and trips Binance's strict step validation.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import Any

log = logging.getLogger(__name__)

# ERROR-20260511-9: defensive guard. Binance USDT-M perp symbols are strictly
# ASCII (e.g. ``BTCUSDT``); a display-name field like "币安人生USDT" leaking
# into the symbol slot crashed the engine with -1100 'Illegal characters'.
# Any symbol that does not match this regex is dropped at parse time so it
# never reaches the screener, router, or live-execution surface.
ASCII_USDT_SYMBOL_RE = re.compile(r"^[A-Z0-9]+USDT$")


def is_valid_ascii_usdt_symbol(symbol: str) -> bool:
    """Return True iff ``symbol`` is a plain ASCII USDT-quoted perp symbol.

    See ERROR-20260511-9 in memory/execution-errors.md.
    """
    return isinstance(symbol, str) and bool(ASCII_USDT_SYMBOL_RE.match(symbol))

# ----------------------------------------------------------------------------
# Filter dataclasses
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class PriceFilter:
    min_price: Decimal
    max_price: Decimal
    tick_size: Decimal


@dataclass(frozen=True)
class LotSizeFilter:
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal


@dataclass(frozen=True)
class MinNotionalFilter:
    notional: Decimal


@dataclass(frozen=True)
class PercentPriceFilter:
    multiplier_up: Decimal
    multiplier_down: Decimal


@dataclass(frozen=True)
class SymbolSpec:
    """Everything we need to validate and round an order for one symbol."""

    symbol: str
    base_asset: str
    quote_asset: str
    contract_type: str
    status: str
    price_precision: int
    quantity_precision: int

    price_filter: PriceFilter
    lot_size_filter: LotSizeFilter
    market_lot_size_filter: LotSizeFilter
    min_notional_filter: MinNotionalFilter
    percent_price_filter: PercentPriceFilter | None  # not always present

    # Convenience flags computed from data, not filters.
    is_perpetual: bool
    is_usdt_quoted: bool
    is_decimal_priced: bool  # tickSize < 1 — i.e. price has decimals


# ----------------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------------


def _D(x: Any) -> Decimal:
    """Parse a Binance string-or-number value as Decimal without float loss."""
    return Decimal(str(x))


def parse_symbol_spec(raw: dict[str, Any]) -> SymbolSpec:
    """Convert one entry of `exchangeInfo.symbols` into a typed `SymbolSpec`.

    Raises:
        KeyError if a required filter is missing — callers should treat such
        symbols as untradeable and skip them.
    """
    flt: dict[str, dict[str, Any]] = {f["filterType"]: f for f in raw["filters"]}

    price_filter = PriceFilter(
        min_price=_D(flt["PRICE_FILTER"]["minPrice"]),
        max_price=_D(flt["PRICE_FILTER"]["maxPrice"]),
        tick_size=_D(flt["PRICE_FILTER"]["tickSize"]),
    )
    lot_filter = LotSizeFilter(
        min_qty=_D(flt["LOT_SIZE"]["minQty"]),
        max_qty=_D(flt["LOT_SIZE"]["maxQty"]),
        step_size=_D(flt["LOT_SIZE"]["stepSize"]),
    )
    market_lot_filter = LotSizeFilter(
        min_qty=_D(flt["MARKET_LOT_SIZE"]["minQty"]),
        max_qty=_D(flt["MARKET_LOT_SIZE"]["maxQty"]),
        step_size=_D(flt["MARKET_LOT_SIZE"]["stepSize"]),
    )
    min_notional = MinNotionalFilter(
        notional=_D(flt["MIN_NOTIONAL"]["notional"])
    )

    percent_price = None
    if "PERCENT_PRICE" in flt:
        pp = flt["PERCENT_PRICE"]
        percent_price = PercentPriceFilter(
            multiplier_up=_D(pp["multiplierUp"]),
            multiplier_down=_D(pp["multiplierDown"]),
        )

    quote_asset = raw.get("quoteAsset", "")
    contract_type = raw.get("contractType", "")
    return SymbolSpec(
        symbol=raw["symbol"],
        base_asset=raw.get("baseAsset", ""),
        quote_asset=quote_asset,
        contract_type=contract_type,
        status=raw.get("status", ""),
        price_precision=int(raw.get("pricePrecision", 0)),
        quantity_precision=int(raw.get("quantityPrecision", 0)),
        price_filter=price_filter,
        lot_size_filter=lot_filter,
        market_lot_size_filter=market_lot_filter,
        min_notional_filter=min_notional,
        percent_price_filter=percent_price,
        is_perpetual=contract_type == "PERPETUAL",
        is_usdt_quoted=quote_asset == "USDT",
        is_decimal_priced=price_filter.tick_size < Decimal("1"),
    )


def parse_exchange_info(exchange_info: dict[str, Any]) -> dict[str, SymbolSpec]:
    """Parse the full `exchangeInfo` payload into a {symbol: SymbolSpec} map.

    Symbols missing a required filter are skipped silently — they're rare and
    usually represent in-flight delistings.
    """
    out: dict[str, SymbolSpec] = {}
    for raw in exchange_info.get("symbols", []):
        try:
            spec = parse_symbol_spec(raw)
        except KeyError:
            continue
        # ERROR-20260511-9: drop any symbol that is not plain ASCII USDT.
        # This guards against display-name leakage (e.g. "币安人生USDT")
        # that would otherwise crash Binance's newClientOrderId regex.
        if not is_valid_ascii_usdt_symbol(spec.symbol):
            log.warning(
                "[NON_ASCII_SYMBOL_DROPPED] symbol=%r rejected by ASCII guard",
                spec.symbol,
            )
            continue
        out[spec.symbol] = spec
    return out


# ----------------------------------------------------------------------------
# Rounding helpers
# ----------------------------------------------------------------------------


def round_to_step(value: Decimal, step: Decimal, *, mode: str = "down") -> Decimal:
    """Round ``value`` down (default) or up to a multiple of ``step``.

    Binance's step filters require *exact* multiples, not "close enough". We
    use Decimal-only math to avoid accumulating float drift when stepping
    through, e.g., 0.00000001 ticks.
    """
    if step <= 0:
        return value
    rounding = ROUND_DOWN if mode == "down" else ROUND_UP
    # quantize by step: floor(value / step) * step  (or ceil)
    quotient = (value / step).quantize(Decimal("1"), rounding=rounding)
    return (quotient * step).normalize() if (quotient * step) != Decimal("0") else Decimal("0")


def round_price(spec: SymbolSpec, price: Decimal, *, mode: str = "down") -> Decimal:
    return round_to_step(price, spec.price_filter.tick_size, mode=mode)


def round_qty(spec: SymbolSpec, qty: Decimal, *, mode: str = "down") -> Decimal:
    return round_to_step(qty, spec.lot_size_filter.step_size, mode=mode)


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class FilterValidation:
    ok: bool
    violations: tuple[str, ...]


def validate_order(
    spec: SymbolSpec,
    *,
    price: Decimal | None,
    quantity: Decimal,
    is_market: bool = False,
) -> FilterValidation:
    """Check an order against PRICE_FILTER, LOT_SIZE, MARKET_LOT_SIZE, MIN_NOTIONAL.

    For a market order pass ``price=None`` (notional is then validated against
    a caller-supplied reference price elsewhere) or pass the current mark price
    so MIN_NOTIONAL can still be enforced.

    Returns a FilterValidation listing every violation — we want the position
    sizer to see *all* problems at once, not one at a time.
    """
    violations: list[str] = []

    # PRICE_FILTER
    if price is not None:
        pf = spec.price_filter
        if price < pf.min_price:
            violations.append(f"PRICE_FILTER: price {price} < minPrice {pf.min_price}")
        elif price > pf.max_price:
            violations.append(f"PRICE_FILTER: price {price} > maxPrice {pf.max_price}")
        elif pf.tick_size > 0 and (price % pf.tick_size) != 0:
            violations.append(
                f"PRICE_FILTER: price {price} is not a multiple of tickSize {pf.tick_size}"
            )

    # LOT_SIZE / MARKET_LOT_SIZE
    lot = spec.market_lot_size_filter if is_market else spec.lot_size_filter
    if quantity < lot.min_qty:
        violations.append(f"{'MARKET_' if is_market else ''}LOT_SIZE: qty {quantity} < minQty {lot.min_qty}")
    elif quantity > lot.max_qty:
        violations.append(f"{'MARKET_' if is_market else ''}LOT_SIZE: qty {quantity} > maxQty {lot.max_qty}")
    elif lot.step_size > 0 and (quantity % lot.step_size) != 0:
        violations.append(
            f"{'MARKET_' if is_market else ''}LOT_SIZE: qty {quantity} not a multiple of stepSize {lot.step_size}"
        )

    # MIN_NOTIONAL
    if price is not None:
        notional = price * quantity
        min_notional = spec.min_notional_filter.notional
        if notional < min_notional:
            violations.append(f"MIN_NOTIONAL: price*qty {notional} < {min_notional}")

    return FilterValidation(ok=not violations, violations=tuple(violations))


__all__ = [
    "PriceFilter",
    "LotSizeFilter",
    "MinNotionalFilter",
    "PercentPriceFilter",
    "SymbolSpec",
    "FilterValidation",
    "parse_symbol_spec",
    "parse_exchange_info",
    "round_to_step",
    "round_price",
    "round_qty",
    "validate_order",
    "is_valid_ascii_usdt_symbol",
    "ASCII_USDT_SYMBOL_RE",
]
