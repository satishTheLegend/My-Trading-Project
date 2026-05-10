"""Token Screener — scan Binance USDT-M perps for tradeable candidates.

Pipeline (one weight-1 + one weight-40 + one weight-10 = ~51 weight per scan):

  1. exchangeInfo                   → filter to TRADING + PERPETUAL + USDT-quoted symbols
  2. ticker/24hr (no symbol)        → quoteVolume, priceChangePct, range
  3. premiumIndex (no symbol)       → markPrice, lastFundingRate (cheap context)

After that, hard filters drop:
  - non-decimal-priced symbols (per user preference for small-caps)
  - illiquid symbols (24h quote volume below threshold)
  - symbols on the user avoid-list
  - symbols already represented by an open position
  - symbols showing extreme funding (crowded-trade warning)

Surviving candidates are scored on a composite of:
  - relative volume (vs symbol's recent baseline if known, else absolute)
  - price-change magnitude (volatility we can trade)
  - 24h range (intraday opportunity proxy)
  - funding-rate moderation (extreme funding is a *negative*)

Output is a `ScreeningResult` with both kept and dropped lists — the dropped
list is intentionally exposed because the No-Trade Engine and Journal Agent
care about *why* candidates were rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from .market_data import (
    MarketData,
    MarkPriceSnapshot,
    Ticker24h,
)
from .symbol_filters import SymbolSpec, parse_exchange_info


# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ScreeningConfig:
    decimal_priced_only: bool = True
    min_24h_quote_volume_usdt: Decimal = Decimal("5000000")    # 5M USDT
    max_spread_bps: Decimal = Decimal("20")                    # 0.20 %
    # Funding-rate is per-8h. ±0.5 % per 8h is already extreme.
    max_abs_funding_rate: Decimal = Decimal("0.005")
    # Drop tokens that moved more than 30% in 24h — usually post-listing chaos
    # or a wick caused by thin liquidity. Re-enable for "short-after-pump" with
    # an explicit override.
    max_abs_24h_change_pct: Decimal = Decimal("30")
    # Require at least this much absolute 24h move to consider it tradeable
    # at all.
    min_abs_24h_change_pct: Decimal = Decimal("1.5")
    max_candidates: int = 25
    # Symbols the user explicitly avoids. Loaded from memory/user-rules.md
    # by the orchestrator and passed in.
    avoid_list: tuple[str, ...] = ()
    # Symbols we already have a position on — never duplicate.
    already_open: tuple[str, ...] = ()


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateScore:
    symbol: str
    score: float
    last_price: Decimal
    quote_volume_usdt: Decimal
    price_change_pct_24h: Decimal
    range_pct_24h: Decimal              # (high - low) / open * 100
    funding_rate_8h: Decimal | None
    spec: SymbolSpec

    def to_jsonable(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": round(self.score, 4),
            "last_price": str(self.last_price),
            "quote_volume_usdt": str(self.quote_volume_usdt),
            "price_change_pct_24h": str(self.price_change_pct_24h),
            "range_pct_24h": str(self.range_pct_24h),
            "funding_rate_8h": str(self.funding_rate_8h) if self.funding_rate_8h is not None else None,
            "is_decimal_priced": self.spec.is_decimal_priced,
            "tick_size": str(self.spec.price_filter.tick_size),
        }


@dataclass(frozen=True)
class Rejection:
    symbol: str
    reason: str

    def to_jsonable(self) -> dict:
        return {"symbol": self.symbol, "reason": self.reason}


@dataclass(frozen=True)
class ScreeningResult:
    candidates: tuple[CandidateScore, ...]
    rejected: tuple[Rejection, ...]
    universe_size: int       # number of TRADING perpetual USDT pairs we considered

    def to_jsonable(self) -> dict:
        return {
            "candidates": [c.to_jsonable() for c in self.candidates],
            "rejected_count": len(self.rejected),
            # only the top 50 rejections to keep payloads manageable
            "rejected_sample": [r.to_jsonable() for r in self.rejected[:50]],
            "universe_size": self.universe_size,
        }


# ----------------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------------


def run_screener(
    market: MarketData,
    config: ScreeningConfig | None = None,
) -> ScreeningResult:
    cfg = config or ScreeningConfig()

    # Step 1 — exchangeInfo (weight 1)
    raw_info = market.get_exchange_info()
    specs = parse_exchange_info(raw_info)

    # Universe = TRADING + PERPETUAL + USDT-quoted
    universe: dict[str, SymbolSpec] = {
        s: spec for s, spec in specs.items()
        if spec.status == "TRADING" and spec.is_perpetual and spec.is_usdt_quoted
    }

    # Step 2 — 24hr tickers (weight 40)
    tickers = {t.symbol: t for t in market.get_all_tickers_24h()}

    # Step 3 — premium index (weight 10)
    funding = {m.symbol: m for m in market.get_all_mark_prices()}

    rejected: list[Rejection] = []
    kept: list[CandidateScore] = []

    avoid = set(cfg.avoid_list)
    open_set = set(cfg.already_open)

    for symbol, spec in universe.items():
        if symbol in avoid:
            rejected.append(Rejection(symbol, "in user avoid-list"))
            continue
        if symbol in open_set:
            rejected.append(Rejection(symbol, "position already open"))
            continue
        if cfg.decimal_priced_only and not spec.is_decimal_priced:
            rejected.append(Rejection(symbol, f"not decimal-priced (tickSize={spec.price_filter.tick_size})"))
            continue

        t = tickers.get(symbol)
        if t is None:
            rejected.append(Rejection(symbol, "no 24h ticker available"))
            continue

        if t.quote_volume < cfg.min_24h_quote_volume_usdt:
            rejected.append(Rejection(
                symbol, f"24h quoteVolume {t.quote_volume} < {cfg.min_24h_quote_volume_usdt}"
            ))
            continue

        abs_change = abs(t.price_change_pct)
        if abs_change > cfg.max_abs_24h_change_pct:
            rejected.append(Rejection(
                symbol, f"24h change |{t.price_change_pct}%| > {cfg.max_abs_24h_change_pct}%"
            ))
            continue
        if abs_change < cfg.min_abs_24h_change_pct:
            rejected.append(Rejection(
                symbol, f"24h change |{t.price_change_pct}%| < {cfg.min_abs_24h_change_pct}%"
            ))
            continue

        m = funding.get(symbol)
        funding_rate: Decimal | None = m.last_funding_rate if m else None
        if funding_rate is not None and abs(funding_rate) > cfg.max_abs_funding_rate:
            rejected.append(Rejection(
                symbol, f"funding {funding_rate} exceeds ±{cfg.max_abs_funding_rate} per 8h"
            ))
            continue

        # Range proxy for intraday opportunity.
        range_pct = (
            (t.high_price - t.low_price) / t.open_price * Decimal("100")
            if t.open_price > 0 else Decimal("0")
        )

        kept.append(CandidateScore(
            symbol=symbol,
            score=_score(t, m, range_pct),
            last_price=t.last_price,
            quote_volume_usdt=t.quote_volume,
            price_change_pct_24h=t.price_change_pct,
            range_pct_24h=range_pct,
            funding_rate_8h=funding_rate,
            spec=spec,
        ))

    kept.sort(key=lambda c: c.score, reverse=True)
    kept = kept[: cfg.max_candidates]

    return ScreeningResult(
        candidates=tuple(kept),
        rejected=tuple(rejected),
        universe_size=len(universe),
    )


def _score(t: Ticker24h, m: MarkPriceSnapshot | None, range_pct: Decimal) -> float:
    """Composite score in roughly [0, 100]. Higher = better candidate.

    Components, all clipped:
      - log10(quoteVolume / 1M)        × 10   (caps ~30 for $1B daily)
      - |24h change %|                 ×  1   (clipped at 25)
      - 24h range %                    ×  1   (clipped at 25)
      - funding-rate penalty           — quadratic above 0.001/8h
    """
    import math

    vol_score = 0.0
    qv = float(t.quote_volume)
    if qv > 1_000_000:
        vol_score = math.log10(qv / 1_000_000) * 10.0
    vol_score = min(vol_score, 30.0)

    change_score = min(abs(float(t.price_change_pct)), 25.0)
    range_score = min(float(range_pct), 25.0)

    funding_penalty = 0.0
    if m is not None:
        f = abs(float(m.last_funding_rate))
        if f > 0.001:
            # 0.001 → 0, 0.005 → 16
            funding_penalty = min(((f - 0.001) * 4000.0) ** 2, 25.0)

    score = vol_score + change_score + range_score - funding_penalty
    return max(score, 0.0)


__all__ = [
    "ScreeningConfig",
    "CandidateScore",
    "Rejection",
    "ScreeningResult",
    "run_screener",
]
