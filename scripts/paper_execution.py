"""Paper execution — realistic entry-fill simulation.

Replaces the placeholder "log a proposal" step in Phase 2 with a depth-aware
fill simulator. Given an order book and a desired qty, walks the book level
by level to compute the volume-weighted average fill price. Adds taker fee
and reports residual unfilled qty.

This module never sends a real order. It exists so paper trades have honest
fill prices (slippage matters for small-cap decimal-priced tokens) and so the
journal records realistic PnL.

Phase 4 will add a `live_execution.py` sibling that wraps the same interface
but routes through python-binance / ccxt.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .market_data import OrderBook, OrderBookLevel
from .risk_engine import DEFAULT_TAKER_FEE


@dataclass(frozen=True)
class PaperFill:
    """Result of a simulated entry."""

    side: str                    # "LONG" | "SHORT"
    requested_qty: Decimal
    filled_qty: Decimal          # may be < requested if book runs out
    average_price: Decimal       # VWAP across consumed levels
    levels_consumed: int
    notional_usdt: Decimal       # average_price * filled_qty
    fees_usdt: Decimal           # taker fee on the fill side only (entry)
    slippage_bps: Decimal        # |avg - reference| / reference * 10000
    reference_price: Decimal     # mid price at fill time
    is_complete: bool            # filled_qty == requested_qty
    notes: str

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "side": self.side,
            "requested_qty": str(self.requested_qty),
            "filled_qty": str(self.filled_qty),
            "average_price": str(self.average_price),
            "levels_consumed": self.levels_consumed,
            "notional_usdt": str(self.notional_usdt),
            "fees_usdt": str(self.fees_usdt),
            "slippage_bps": str(self.slippage_bps),
            "reference_price": str(self.reference_price),
            "is_complete": self.is_complete,
            "notes": self.notes,
        }


def simulate_market_fill(
    side: str,
    qty: Decimal,
    book: OrderBook,
    *,
    fee_rate: Decimal = DEFAULT_TAKER_FEE,
) -> PaperFill:
    """Simulate filling a market order against the live order book.

    A LONG buys from the asks; a SHORT sells into the bids. We walk the
    appropriate side level-by-level until ``qty`` is filled or the visible
    book is exhausted.

    Returns a `PaperFill`. If the book is too thin to fully fill, the caller
    (Risk Manager) should reject the trade — sending the partial would put
    real money at unknown slippage in a live cycle.
    """
    if side not in ("LONG", "SHORT"):
        raise ValueError("side must be LONG or SHORT")
    if qty <= 0:
        raise ValueError("qty must be > 0")

    levels: tuple[OrderBookLevel, ...] = book.asks if side == "LONG" else book.bids
    if not levels:
        return PaperFill(
            side=side,
            requested_qty=qty,
            filled_qty=Decimal("0"),
            average_price=Decimal("0"),
            levels_consumed=0,
            notional_usdt=Decimal("0"),
            fees_usdt=Decimal("0"),
            slippage_bps=Decimal("0"),
            reference_price=Decimal("0"),
            is_complete=False,
            notes="empty order book",
        )

    reference = book.mid_price or levels[0].price
    remaining = qty
    filled = Decimal("0")
    cost = Decimal("0")
    consumed = 0
    for lvl in levels:
        consumed += 1
        take = min(remaining, lvl.quantity)
        cost += take * lvl.price
        filled += take
        remaining -= take
        if remaining <= 0:
            break

    if filled <= 0:
        return PaperFill(
            side=side, requested_qty=qty, filled_qty=Decimal("0"),
            average_price=Decimal("0"), levels_consumed=consumed,
            notional_usdt=Decimal("0"), fees_usdt=Decimal("0"),
            slippage_bps=Decimal("0"), reference_price=reference,
            is_complete=False, notes="no liquidity",
        )

    avg_price = cost / filled
    notional = avg_price * filled
    fees = notional * fee_rate
    slippage_bps = abs(avg_price - reference) / reference * Decimal("10000") if reference > 0 else Decimal("0")
    is_complete = remaining <= 0

    notes = ""
    if not is_complete:
        notes = f"partial fill: book exhausted after {filled}/{qty}"

    return PaperFill(
        side=side,
        requested_qty=qty,
        filled_qty=filled,
        average_price=avg_price,
        levels_consumed=consumed,
        notional_usdt=notional,
        fees_usdt=fees,
        slippage_bps=slippage_bps,
        reference_price=reference,
        is_complete=is_complete,
        notes=notes,
    )


def simulate_limit_fill(
    side: str,
    qty: Decimal,
    limit_price: Decimal,
    book: OrderBook,
    *,
    fee_rate: Decimal = DEFAULT_TAKER_FEE,
    aggressive_taker_if_crossed: bool = True,
) -> PaperFill:
    """Simulate a LIMIT order that may or may not cross the spread immediately.

    If ``limit_price`` would cross (LONG limit ≥ best ask, SHORT limit ≤ best
    bid) we treat the cross-fraction as a taker fill. Anything beyond the
    limit is treated as unfilled — paper mode does not assume the order rests
    on the book.
    """
    if side == "LONG":
        # Take from asks at price <= limit
        eligible = tuple(lvl for lvl in book.asks if lvl.price <= limit_price)
    else:
        eligible = tuple(lvl for lvl in book.bids if lvl.price >= limit_price)

    if not eligible:
        # No immediate fill; in paper mode we treat as unfilled.
        return PaperFill(
            side=side, requested_qty=qty, filled_qty=Decimal("0"),
            average_price=Decimal("0"), levels_consumed=0,
            notional_usdt=Decimal("0"), fees_usdt=Decimal("0"),
            slippage_bps=Decimal("0"),
            reference_price=book.mid_price or Decimal("0"),
            is_complete=False,
            notes="limit price not crossed; no immediate fill",
        )

    # Build a synthetic "book" of just the eligible side and reuse the market
    # fill logic — DRY.
    bids = eligible if side == "SHORT" else book.bids
    asks = eligible if side == "LONG" else book.asks
    synthetic = OrderBook(
        symbol=book.symbol,
        last_update_id=book.last_update_id,
        bids=bids,
        asks=asks,
        transaction_time_ms=book.transaction_time_ms,
    )
    fill = simulate_market_fill(side, qty, synthetic, fee_rate=fee_rate)
    if not fill.is_complete and aggressive_taker_if_crossed:
        # The limit was set well past the visible book — caller wanted to fill
        # all qty but the eligible eligible levels weren't enough. We surface
        # the partial honestly; live limits would just rest the unfilled
        # remainder on the book.
        notes = (fill.notes + "; ") if fill.notes else ""
        notes += "remainder unfilled (would rest on book in live mode)"
        fill = PaperFill(**{**fill.__dict__, "notes": notes})
    return fill


__all__ = [
    "PaperFill",
    "simulate_market_fill",
    "simulate_limit_fill",
]
