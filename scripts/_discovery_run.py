"""Ad-hoc discovery driver — runs the screener + light research.

Not part of the cycle scripts. Invoked by the Market Intelligence Agent during
news/sentiment/screener discovery passes.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal

from scripts.binance_client import BinanceClient
from scripts.market_data import MarketData
from scripts.token_screener import ScreeningConfig, run_screener


AVOID_SYMBOLS: tuple[str, ...] = ()
ALREADY_OPEN: tuple[str, ...] = (
    "ZBTUSDT",
    "ALCHUSDT",
    "FHEUSDT",
    "TRUTHUSDT",
)


def main() -> int:
    client = BinanceClient()
    market = MarketData(client)

    cfg = ScreeningConfig(
        decimal_priced_only=True,
        min_24h_quote_volume_usdt=Decimal("5000000"),
        max_candidates=30,
        avoid_list=AVOID_SYMBOLS,
        already_open=ALREADY_OPEN,
    )
    result = run_screener(market, cfg)

    # Light research on top 8
    top = result.candidates[:8]
    research: list[dict] = []
    for c in top:
        entry = {
            "symbol": c.symbol,
            "score": round(c.score, 2),
            "last_price": str(c.last_price),
            "qv_usdt": str(c.quote_volume_usdt),
            "change_24h_pct": str(c.price_change_pct_24h),
            "range_24h_pct": str(round(c.range_pct_24h, 2)),
            "funding_8h": str(c.funding_rate_8h) if c.funding_rate_8h is not None else None,
        }
        # Open Interest 8h delta via /fapi/v1/openInterestHist
        try:
            oi_hist = client.get(
                "/futures/data/openInterestHist",
                params={"symbol": c.symbol, "period": "1h", "limit": 9},
            )
            if len(oi_hist) >= 9:
                oi_now = Decimal(str(oi_hist[-1]["sumOpenInterest"]))
                oi_8h_ago = Decimal(str(oi_hist[0]["sumOpenInterest"]))
                if oi_8h_ago > 0:
                    delta = (oi_now - oi_8h_ago) / oi_8h_ago * Decimal("100")
                    entry["oi_change_8h_pct"] = str(round(delta, 2))
                else:
                    entry["oi_change_8h_pct"] = None
            else:
                entry["oi_change_8h_pct"] = None
        except Exception as exc:
            entry["oi_change_8h_pct"] = f"err:{type(exc).__name__}"

        # 1h candles for structure (last 12h)
        try:
            klines = market.get_klines(symbol=c.symbol, interval="1h", limit=12)
            if klines:
                opens = [float(k.open) for k in klines]
                closes = [float(k.close) for k in klines]
                highs = [float(k.high) for k in klines]
                lows = [float(k.low) for k in klines]
                last_close = closes[-1]
                hh = max(highs)
                ll = min(lows)
                entry["1h_high_12"] = hh
                entry["1h_low_12"] = ll
                entry["dist_from_12h_high_pct"] = round((last_close - hh) / hh * 100, 2)
                entry["dist_from_12h_low_pct"] = round((last_close - ll) / ll * 100, 2)
                # Trend bias: count up vs down candles in last 6
                ups = sum(1 for i in range(-6, 0) if closes[i] > opens[i])
                entry["1h_ups_last6"] = ups
        except Exception as exc:
            entry["candles_err"] = type(exc).__name__

        # 24h high/low + distance
        try:
            t = next((x for x in market.get_all_tickers_24h() if x.symbol == c.symbol), None)
            if t:
                entry["24h_high"] = str(t.high_price)
                entry["24h_low"] = str(t.low_price)
                if t.high_price > 0:
                    entry["dist_from_24h_high_pct"] = str(
                        round((c.last_price - t.high_price) / t.high_price * Decimal("100"), 2)
                    )
                if t.low_price > 0:
                    entry["dist_from_24h_low_pct"] = str(
                        round((c.last_price - t.low_price) / t.low_price * Decimal("100"), 2)
                    )
        except Exception as exc:
            entry["ticker_err"] = type(exc).__name__

        research.append(entry)

    payload = {
        "universe_size": result.universe_size,
        "candidates_count": len(result.candidates),
        "top": [c.to_jsonable() for c in result.candidates[:20]],
        "research": research,
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
