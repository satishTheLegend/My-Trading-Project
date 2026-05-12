"""Symbol-filter math: rounding, validation, decimal correctness."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.symbol_filters import (
    LotSizeFilter,
    MinNotionalFilter,
    PercentPriceFilter,
    PriceFilter,
    SymbolSpec,
    is_valid_ascii_usdt_symbol,
    parse_exchange_info,
    parse_symbol_spec,
    round_qty,
    round_price,
    round_to_step,
    validate_order,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def doge_spec() -> SymbolSpec:
    """A DOGE-like decimal-priced symbol with realistic Binance filters."""
    raw = {
        "symbol": "DOGEUSDT",
        "pair": "DOGEUSDT",
        "contractType": "PERPETUAL",
        "status": "TRADING",
        "baseAsset": "DOGE",
        "quoteAsset": "USDT",
        "pricePrecision": 5,
        "quantityPrecision": 0,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.00001",
             "maxPrice": "1000", "tickSize": "0.00001"},
            {"filterType": "LOT_SIZE", "minQty": "1", "maxQty": "10000000",
             "stepSize": "1"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "1",
             "maxQty": "5900000", "stepSize": "1"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
            {"filterType": "MAX_NUM_ORDERS", "limit": 200},
            {"filterType": "PERCENT_PRICE", "multiplierUp": "1.15",
             "multiplierDown": "0.85", "multiplierDecimal": "4"},
        ],
    }
    return parse_symbol_spec(raw)


# ---------------------------------------------------------------------------
# round_to_step
# ---------------------------------------------------------------------------


def test_round_to_step_down_basic():
    assert round_to_step(Decimal("0.123456"), Decimal("0.001"), mode="down") == Decimal("0.123")


def test_round_to_step_up_basic():
    assert round_to_step(Decimal("0.1231"), Decimal("0.001"), mode="up") == Decimal("0.124")


def test_round_to_step_exact_multiple():
    # Exactly on a step → stays the same.
    assert round_to_step(Decimal("0.05"), Decimal("0.01"), mode="down") == Decimal("0.05")


def test_round_to_step_decimal_priced_token():
    """0.07654 with tick 0.00001 → 0.07654 (already on step)."""
    assert round_to_step(Decimal("0.07654"), Decimal("0.00001"), mode="down") == Decimal("0.07654")


def test_round_to_step_decimal_priced_truncation():
    """0.076549 with tick 0.00001 → 0.07654 (truncate, not round-up)."""
    assert round_to_step(Decimal("0.076549"), Decimal("0.00001"), mode="down") == Decimal("0.07654")


def test_round_to_step_zero_step_passthrough():
    """A zero step is meaningless and must not divide-by-zero."""
    assert round_to_step(Decimal("1.234"), Decimal("0"), mode="down") == Decimal("1.234")


# ---------------------------------------------------------------------------
# parse_symbol_spec
# ---------------------------------------------------------------------------


def test_parse_doge_spec_flags(doge_spec: SymbolSpec):
    assert doge_spec.symbol == "DOGEUSDT"
    assert doge_spec.is_perpetual is True
    assert doge_spec.is_usdt_quoted is True
    assert doge_spec.is_decimal_priced is True
    assert doge_spec.price_filter.tick_size == Decimal("0.00001")
    assert doge_spec.lot_size_filter.step_size == Decimal("1")
    assert doge_spec.min_notional_filter.notional == Decimal("5")


def test_parse_skips_missing_required_filter():
    """A symbol with no MIN_NOTIONAL filter must raise (callers skip these)."""
    raw = {
        "symbol": "BROKENUSDT", "pair": "BROKENUSDT", "contractType": "PERPETUAL",
        "status": "TRADING", "baseAsset": "BROKEN", "quoteAsset": "USDT",
        "pricePrecision": 4, "quantityPrecision": 0,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.0001",
             "maxPrice": "1000", "tickSize": "0.0001"},
            {"filterType": "LOT_SIZE", "minQty": "1", "maxQty": "10000",
             "stepSize": "1"},
        ],
    }
    with pytest.raises(KeyError):
        parse_symbol_spec(raw)


# ---------------------------------------------------------------------------
# validate_order
# ---------------------------------------------------------------------------


def test_validate_order_passes_clean(doge_spec: SymbolSpec):
    v = validate_order(doge_spec, price=Decimal("0.07654"), quantity=Decimal("100"))
    assert v.ok, v.violations


def test_validate_order_below_min_qty(doge_spec: SymbolSpec):
    v = validate_order(doge_spec, price=Decimal("0.07654"), quantity=Decimal("0"))
    assert not v.ok
    assert any("LOT_SIZE" in m and "minQty" in m for m in v.violations)


def test_validate_order_qty_not_step_multiple(doge_spec: SymbolSpec):
    """DOGE has stepSize=1; qty=10.5 must fail."""
    v = validate_order(doge_spec, price=Decimal("0.07654"), quantity=Decimal("10.5"))
    assert not v.ok
    assert any("multiple of stepSize" in m for m in v.violations)


def test_validate_order_below_min_notional(doge_spec: SymbolSpec):
    """price 0.00001 × 1 = 0.00001 USDT → far below MIN_NOTIONAL=5."""
    v = validate_order(doge_spec, price=Decimal("0.00001"), quantity=Decimal("1"))
    assert not v.ok
    assert any("MIN_NOTIONAL" in m for m in v.violations)


def test_validate_order_price_not_tick_multiple(doge_spec: SymbolSpec):
    # tick is 0.00001; 0.076545 is not a multiple
    v = validate_order(doge_spec, price=Decimal("0.076545"), quantity=Decimal("100"))
    assert not v.ok
    assert any("multiple of tickSize" in m for m in v.violations)


def test_round_qty_floors_correctly(doge_spec: SymbolSpec):
    # raw 153.7 → 153
    assert round_qty(doge_spec, Decimal("153.7"), mode="down") == Decimal("153")


def test_round_price_floors_correctly(doge_spec: SymbolSpec):
    assert round_price(doge_spec, Decimal("0.076549"), mode="down") == Decimal("0.07654")


# ---------------------------------------------------------------------------
# ERROR-20260511-9: ASCII-symbol guard
# ---------------------------------------------------------------------------


def test_ascii_symbol_guard_accepts_normal_symbols():
    assert is_valid_ascii_usdt_symbol("BTCUSDT")
    assert is_valid_ascii_usdt_symbol("DOGEUSDT")
    assert is_valid_ascii_usdt_symbol("1000PEPEUSDT")


def test_ascii_symbol_guard_rejects_non_ascii_display_name():
    # The exact symbol that crashed the engine on 2026-05-11T17:01:36Z.
    assert not is_valid_ascii_usdt_symbol("币安人生USDT")


def test_ascii_symbol_guard_rejects_lowercase_and_non_usdt():
    assert not is_valid_ascii_usdt_symbol("btcusdt")        # lowercase
    assert not is_valid_ascii_usdt_symbol("BTCBUSD")        # wrong quote
    assert not is_valid_ascii_usdt_symbol("")               # empty
    assert not is_valid_ascii_usdt_symbol("BTC-USDT")       # punctuation
    assert not is_valid_ascii_usdt_symbol(None)             # type: ignore[arg-type]


def test_parse_exchange_info_drops_non_ascii_symbol(doge_spec: SymbolSpec):
    """parse_exchange_info must silently skip non-ASCII symbols so they
    never reach the screener, router, or live-execution layer."""
    bad_raw = {
        "symbol": "币安人生USDT", "pair": "币安人生USDT", "contractType": "PERPETUAL",
        "status": "TRADING", "baseAsset": "币安人生", "quoteAsset": "USDT",
        "pricePrecision": 5, "quantityPrecision": 0,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.00001",
             "maxPrice": "1000", "tickSize": "0.00001"},
            {"filterType": "LOT_SIZE", "minQty": "1", "maxQty": "1000", "stepSize": "1"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "1", "maxQty": "1000", "stepSize": "1"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
            {"filterType": "PERCENT_PRICE", "multiplierUp": "1.15",
             "multiplierDown": "0.85", "multiplierDecimal": "4"},
        ],
    }
    good_raw = {
        "symbol": "DOGEUSDT", "pair": "DOGEUSDT", "contractType": "PERPETUAL",
        "status": "TRADING", "baseAsset": "DOGE", "quoteAsset": "USDT",
        "pricePrecision": 5, "quantityPrecision": 0,
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.00001",
             "maxPrice": "1000", "tickSize": "0.00001"},
            {"filterType": "LOT_SIZE", "minQty": "1", "maxQty": "1000", "stepSize": "1"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "1", "maxQty": "1000", "stepSize": "1"},
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
            {"filterType": "PERCENT_PRICE", "multiplierUp": "1.15",
             "multiplierDown": "0.85", "multiplierDecimal": "4"},
        ],
    }
    out = parse_exchange_info({"symbols": [bad_raw, good_raw]})
    assert "币安人生USDT" not in out
    assert "DOGEUSDT" in out
