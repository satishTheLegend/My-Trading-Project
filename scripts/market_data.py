"""High-level Binance USDT-M Futures market data.

Wraps `BinanceClient` and returns clean dataclasses instead of raw JSON. Every
agent above this layer (Token Screener, Token Research, Strategy, Watcher)
should consume these typed objects so that:

  - field names are stable across Binance schema tweaks,
  - all numeric fields are `Decimal` (no float drift on small-cap prices),
  - missing/optional fields are `None` rather than absent keys.

This module is read-only and stateless. No caching here — caching belongs in
the orchestrator's per-cycle context.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from .binance_client import BinanceClient

# Binance accepts these intervals on /fapi/v1/klines:
#   1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M
# We expose a small allowlist; agents stay on this set.
SUPPORTED_INTERVALS = ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d")

# Binance order-book endpoint accepts these limits — anything else returns -1100.
VALID_DEPTH_LIMITS = (5, 10, 20, 50, 100, 500, 1000)


# ----------------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Candle:
    """One kline / candle. All prices use ``Decimal`` for precision safety."""

    open_time_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal           # base-asset volume
    close_time_ms: int
    quote_volume: Decimal     # quote-asset (USDT) volume — what we usually want
    trades: int
    taker_buy_base_volume: Decimal
    taker_buy_quote_volume: Decimal

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def body(self) -> Decimal:
        return abs(self.close - self.open)

    @property
    def range(self) -> Decimal:
        return self.high - self.low

    @property
    def upper_wick(self) -> Decimal:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> Decimal:
        return min(self.open, self.close) - self.low

    @property
    def buy_pressure(self) -> Decimal | None:
        """Taker-buy quote volume / total quote volume. None if zero volume."""
        if self.quote_volume == 0:
            return None
        return self.taker_buy_quote_volume / self.quote_volume


@dataclass(frozen=True)
class Ticker24h:
    symbol: str
    last_price: Decimal
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    price_change_pct: Decimal       # already a percentage (e.g. -2.345 = -2.345%)
    base_volume: Decimal
    quote_volume: Decimal           # USDT volume — primary liquidity proxy
    open_time_ms: int
    close_time_ms: int
    trades: int


@dataclass(frozen=True)
class MarkPriceSnapshot:
    symbol: str
    mark_price: Decimal
    index_price: Decimal | None
    last_funding_rate: Decimal      # e.g. 0.0001 = 0.01% per 8h
    next_funding_time_ms: int
    time_ms: int


@dataclass(frozen=True)
class OrderBookLevel:
    price: Decimal
    quantity: Decimal


@dataclass(frozen=True)
class OrderBook:
    symbol: str
    last_update_id: int
    bids: tuple[OrderBookLevel, ...]   # sorted descending by price
    asks: tuple[OrderBookLevel, ...]   # sorted ascending by price
    transaction_time_ms: int | None

    @property
    def best_bid(self) -> OrderBookLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> OrderBookLevel | None:
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> Decimal | None:
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / Decimal("2")
        return None

    @property
    def spread_bps(self) -> Decimal | None:
        """Spread in basis points relative to mid price. Lower is better."""
        if not (self.best_bid and self.best_ask):
            return None
        mid = self.mid_price
        if mid is None or mid == 0:
            return None
        return (self.best_ask.price - self.best_bid.price) / mid * Decimal("10000")

    def depth_quote_within_pct(self, pct: Decimal, side: str) -> Decimal:
        """Quote-asset (USDT) liquidity available within ``pct`` of mid on ``side``.

        Useful proxy for "can I exit a 100 USDT position without 1% slippage?".
        ``side`` is 'bid' (sell into) or 'ask' (buy into).
        """
        mid = self.mid_price
        if mid is None:
            return Decimal("0")
        side_levels = self.bids if side == "bid" else self.asks
        threshold_low = mid * (Decimal("1") - pct / Decimal("100"))
        threshold_high = mid * (Decimal("1") + pct / Decimal("100"))
        total = Decimal("0")
        for lvl in side_levels:
            if side == "bid" and lvl.price < threshold_low:
                break
            if side == "ask" and lvl.price > threshold_high:
                break
            total += lvl.price * lvl.quantity
        return total


@dataclass(frozen=True)
class OpenInterestSnapshot:
    symbol: str
    open_interest_base: Decimal
    time_ms: int


# ----------------------------------------------------------------------------
# Fetcher
# ----------------------------------------------------------------------------


class MarketData:
    """Typed wrappers around the Binance public market-data endpoints."""

    def __init__(self, client: BinanceClient | None = None) -> None:
        self.client = client or BinanceClient()

    # exchange info ------------------------------------------------------

    def get_exchange_info(self) -> dict[str, Any]:
        return self.client.get("/fapi/v1/exchangeInfo")

    def server_time_ms(self) -> int:
        d = self.client.get("/fapi/v1/time")
        return int(d["serverTime"])

    # candles ------------------------------------------------------------

    def get_klines(
        self,
        symbol: str,
        interval: str,
        *,
        limit: int = 500,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> list[Candle]:
        if interval not in SUPPORTED_INTERVALS:
            raise ValueError(f"unsupported interval {interval!r}; pick from {SUPPORTED_INTERVALS}")
        if not (1 <= limit <= 1500):
            raise ValueError("limit must be in [1, 1500]")
        raw = self.client.get(
            "/fapi/v1/klines",
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
                "startTime": start_ms,
                "endTime": end_ms,
            },
        )
        return [_candle_from_row(row) for row in raw]

    # 24h ticker ---------------------------------------------------------

    def get_ticker_24h(self, symbol: str) -> Ticker24h:
        raw = self.client.get("/fapi/v1/ticker/24hr", params={"symbol": symbol})
        return _ticker_from_dict(raw)

    def get_all_tickers_24h(self) -> list[Ticker24h]:
        """One call returns the full universe — weight 40. Use sparingly."""
        raw = self.client.get("/fapi/v1/ticker/24hr")
        return [_ticker_from_dict(d) for d in raw]

    # mark price + funding ---------------------------------------------

    def get_mark_price(self, symbol: str) -> MarkPriceSnapshot:
        raw = self.client.get("/fapi/v1/premiumIndex", params={"symbol": symbol})
        return _mark_from_dict(raw)

    def get_all_mark_prices(self) -> list[MarkPriceSnapshot]:
        raw = self.client.get("/fapi/v1/premiumIndex")
        return [_mark_from_dict(d) for d in raw]

    # depth -------------------------------------------------------------

    def get_order_book(self, symbol: str, *, limit: int = 50) -> OrderBook:
        if limit not in VALID_DEPTH_LIMITS:
            raise ValueError(f"depth limit must be one of {VALID_DEPTH_LIMITS}")
        raw = self.client.get("/fapi/v1/depth", params={"symbol": symbol, "limit": limit})
        return _orderbook_from_dict(symbol, raw)

    # open interest ----------------------------------------------------

    def get_open_interest(self, symbol: str) -> OpenInterestSnapshot:
        raw = self.client.get("/fapi/v1/openInterest", params={"symbol": symbol})
        return OpenInterestSnapshot(
            symbol=raw["symbol"],
            open_interest_base=Decimal(str(raw["openInterest"])),
            time_ms=int(raw["time"]),
        )


# ----------------------------------------------------------------------------
# Internal converters
# ----------------------------------------------------------------------------


def _candle_from_row(row: list[Any]) -> Candle:
    return Candle(
        open_time_ms=int(row[0]),
        open=Decimal(row[1]),
        high=Decimal(row[2]),
        low=Decimal(row[3]),
        close=Decimal(row[4]),
        volume=Decimal(row[5]),
        close_time_ms=int(row[6]),
        quote_volume=Decimal(row[7]),
        trades=int(row[8]),
        taker_buy_base_volume=Decimal(row[9]),
        taker_buy_quote_volume=Decimal(row[10]),
    )


def _ticker_from_dict(d: dict[str, Any]) -> Ticker24h:
    return Ticker24h(
        symbol=d["symbol"],
        last_price=Decimal(d["lastPrice"]),
        open_price=Decimal(d["openPrice"]),
        high_price=Decimal(d["highPrice"]),
        low_price=Decimal(d["lowPrice"]),
        price_change_pct=Decimal(d["priceChangePercent"]),
        base_volume=Decimal(d["volume"]),
        quote_volume=Decimal(d["quoteVolume"]),
        open_time_ms=int(d["openTime"]),
        close_time_ms=int(d["closeTime"]),
        trades=int(d.get("count", 0)),
    )


def _mark_from_dict(d: dict[str, Any]) -> MarkPriceSnapshot:
    idx = d.get("indexPrice")
    return MarkPriceSnapshot(
        symbol=d["symbol"],
        mark_price=Decimal(d["markPrice"]),
        index_price=Decimal(idx) if idx not in (None, "") else None,
        last_funding_rate=Decimal(d.get("lastFundingRate") or "0"),
        next_funding_time_ms=int(d.get("nextFundingTime") or 0),
        time_ms=int(d.get("time") or 0),
    )


def _orderbook_from_dict(symbol: str, d: dict[str, Any]) -> OrderBook:
    bids = tuple(OrderBookLevel(price=Decimal(p), quantity=Decimal(q)) for p, q in d.get("bids", []))
    asks = tuple(OrderBookLevel(price=Decimal(p), quantity=Decimal(q)) for p, q in d.get("asks", []))
    return OrderBook(
        symbol=symbol,
        last_update_id=int(d.get("lastUpdateId", 0)),
        bids=bids,
        asks=asks,
        transaction_time_ms=int(d["T"]) if d.get("T") is not None else None,
    )


def now_ms() -> int:
    return int(time.time() * 1000)


__all__ = [
    "Candle",
    "Ticker24h",
    "MarkPriceSnapshot",
    "OrderBook",
    "OrderBookLevel",
    "OpenInterestSnapshot",
    "MarketData",
    "SUPPORTED_INTERVALS",
    "VALID_DEPTH_LIMITS",
    "now_ms",
]
