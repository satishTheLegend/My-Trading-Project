"""
trend_runner_scanner.py

Scans Binance USDT-M Futures for the TREND_RUNNER pattern extracted from
the user's USELESSUSDT trade case study (2026-05-11):

  1. 15m: >=7 of last 9 candles GREEN with HH+HL (LONG) or LH+LL (SHORT)
  2. 15m vol-ratio: last 3 bars avg > prior 3 bars avg * 2.0
  3. 5m streak: >=4 consecutive higher closes (LONG) or lower closes (SHORT)
  4. Single 5m bar with vol >= 10M USDT-notional in last 30 min
  5. Funding < +0.02%/8h (LONG) or > -0.02% (SHORT)
  6. OI rising +5% to +15%/h (not parabolic >+30%/h)

Returns symbols sorted by signature score. Diagnostic-only - does not fire trades.

Usage:
  set -a && source .env && set +a
  python -m scripts.trend_runner_scanner

  # or with filter
  python -m scripts.trend_runner_scanner --min-qvol 20000000 --side long
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

CTX = ssl.create_default_context()
BASE = "https://fapi.binance.com"


def _http_get(path: str, params: Optional[dict] = None, timeout: int = 8) -> dict | list:
    url = f"{BASE}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    with urllib.request.urlopen(url, context=CTX, timeout=timeout) as r:
        return json.loads(r.read())


@dataclass
class TrendRunnerSignal:
    symbol: str
    side: str  # LONG or SHORT
    score: int  # 0..6 conditions passed
    last_price: float
    vol_ratio: float
    streak_5m: int
    hh_hl_count: int
    whale_bar_vol: float
    funding_rate: float
    oi_change_pct_1h: float
    rngpos_24h: float
    conditions_met: list[str]
    conditions_failed: list[str]


def fetch_universe(min_qvol_usdt: float) -> list[dict]:
    """Get top symbols by qvol passing ASCII filter."""
    tickers = _http_get("/fapi/v1/ticker/24hr")
    out = []
    import re

    ascii_re = re.compile(r"^[A-Z0-9]+USDT$")
    for t in tickers:
        sym = t.get("symbol", "")
        if not ascii_re.match(sym):
            continue
        if float(t.get("quoteVolume", 0)) < min_qvol_usdt:
            continue
        out.append(t)
    return sorted(out, key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)


def detect_trend_runner(symbol: str, side: str = "LONG") -> Optional[TrendRunnerSignal]:
    """Return signal if symbol matches TREND_RUNNER signature, else None."""
    try:
        k5 = _http_get("/fapi/v1/klines", {"symbol": symbol, "interval": "5m", "limit": 12})
        k15 = _http_get("/fapi/v1/klines", {"symbol": symbol, "interval": "15m", "limit": 10})
        prem = _http_get("/fapi/v1/premiumIndex", {"symbol": symbol})
        ticker = _http_get("/fapi/v1/ticker/24hr", {"symbol": symbol})
        oi_hist = _http_get(
            "/futures/data/openInterestHist",
            {"symbol": symbol, "period": "15m", "limit": 5},
        )
    except Exception:
        return None

    if len(k5) < 10 or len(k15) < 9 or len(oi_hist) < 4:
        return None

    is_long = side == "LONG"
    conditions_met: list[str] = []
    conditions_failed: list[str] = []

    # COND 1: 15m HH+HL count
    hh_hl = 0
    prev_h = prev_l = None
    green_count = 0
    for k in k15[-9:]:
        o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
        is_green = c > o
        if is_long:
            if is_green:
                green_count += 1
            if prev_h and prev_l and h > prev_h and l >= prev_l:
                hh_hl += 1
        else:
            if not is_green:
                green_count += 1
            if prev_h and prev_l and h < prev_h and l <= prev_l:
                hh_hl += 1
        prev_h, prev_l = h, l
    cond1 = green_count >= 7 and hh_hl >= 5
    (conditions_met if cond1 else conditions_failed).append(
        f"COND1_15m_trend(green={green_count}/9,hh_hl={hh_hl})"
    )

    # COND 2: vol-ratio
    vols = [float(k[5]) for k in k15[-9:]]
    last3 = sum(vols[-3:]) / 3
    prior3 = sum(vols[-6:-3]) / 3
    vol_ratio = last3 / prior3 if prior3 > 0 else 0
    cond2 = vol_ratio >= 2.0
    (conditions_met if cond2 else conditions_failed).append(f"COND2_vol_ratio({vol_ratio:.2f})")

    # COND 3: 5m streak
    streak = 0
    prev_c = None
    for k in k5[-10:]:
        c = float(k[4])
        if prev_c is not None:
            if (is_long and c > prev_c) or (not is_long and c < prev_c):
                streak += 1
            else:
                streak = 0
        prev_c = c
    cond3 = streak >= 4
    (conditions_met if cond3 else conditions_failed).append(f"COND3_5m_streak({streak})")

    # COND 4: whale-bar vol >= 10M USDT notional in last 6 bars (30 min)
    whale_vol = 0.0
    for k in k5[-6:]:
        c = float(k[4])
        v = float(k[5])
        notional = c * v
        if notional > whale_vol:
            whale_vol = notional
    cond4 = whale_vol >= 10_000_000
    (conditions_met if cond4 else conditions_failed).append(f"COND4_whale_bar({whale_vol/1e6:.1f}M)")

    # COND 5: funding
    funding = float(prem.get("lastFundingRate", 0))
    cond5 = (is_long and funding < 0.0002) or (not is_long and funding > -0.0002)
    (conditions_met if cond5 else conditions_failed).append(f"COND5_funding({funding*100:.4f}%)")

    # COND 6: OI rising at healthy pace (not parabolic)
    oi_now = float(oi_hist[-1]["sumOpenInterest"])
    oi_1h_ago = float(oi_hist[0]["sumOpenInterest"])  # 4 bars ago = 1h
    oi_change_pct = (oi_now - oi_1h_ago) / oi_1h_ago * 100 if oi_1h_ago > 0 else 0
    # For LONG: want OI rising (positive). For SHORT: want OI rising (squeeze fuel) or stable
    if is_long:
        cond6 = 3 <= oi_change_pct <= 30
    else:
        cond6 = -10 <= oi_change_pct <= 20
    (conditions_met if cond6 else conditions_failed).append(f"COND6_OI({oi_change_pct:+.2f}%/h)")

    last_price = float(prem.get("markPrice", k5[-1][4]))
    high24 = float(ticker["highPrice"])
    low24 = float(ticker["lowPrice"])
    rngpos = (last_price - low24) / (high24 - low24) if high24 > low24 else 0.5

    score = sum([cond1, cond2, cond3, cond4, cond5, cond6])
    return TrendRunnerSignal(
        symbol=symbol,
        side=side,
        score=score,
        last_price=last_price,
        vol_ratio=vol_ratio,
        streak_5m=streak,
        hh_hl_count=hh_hl,
        whale_bar_vol=whale_vol,
        funding_rate=funding,
        oi_change_pct_1h=oi_change_pct,
        rngpos_24h=rngpos,
        conditions_met=conditions_met,
        conditions_failed=conditions_failed,
    )


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--min-qvol", type=float, default=20_000_000)
    p.add_argument("--top", type=int, default=30, help="top N symbols by qvol to scan")
    p.add_argument("--side", choices=["long", "short", "both"], default="both")
    p.add_argument("--min-score", type=int, default=4, help="require >=N of 6 conditions")
    args = p.parse_args(argv)

    print(f"=== TREND_RUNNER SCANNER ===")
    print(f"Scanning Binance USDT-M Futures (qvol >= ${args.min_qvol/1e6:.0f}M, top {args.top}, side={args.side}, min-score={args.min_score}/6)")
    universe = fetch_universe(args.min_qvol)[: args.top]
    print(f"Universe: {len(universe)} symbols")

    sides = ["LONG", "SHORT"] if args.side == "both" else [args.side.upper()]
    matches: list[TrendRunnerSignal] = []
    for t in universe:
        sym = t["symbol"]
        for side in sides:
            sig = detect_trend_runner(sym, side=side)
            if sig and sig.score >= args.min_score:
                matches.append(sig)
        time.sleep(0.08)  # rate-limit

    # Sort by score, then by recent move size
    matches.sort(key=lambda s: (s.score, s.streak_5m, s.vol_ratio), reverse=True)

    print(f"\n=== MATCHES ({len(matches)}) ===")
    if not matches:
        print("No symbols matched the TREND_RUNNER signature today at this threshold.")
        return 0

    for sig in matches:
        flag = "🎯" if sig.score == 6 else ("⭐" if sig.score == 5 else "•")
        print(f"\n{flag} {sig.symbol} {sig.side} (score {sig.score}/6)")
        print(f"  Price ${sig.last_price:.5f}  rngpos {sig.rngpos_24h:.2f}  funding {sig.funding_rate*100:.4f}%")
        print(f"  15m HH+HL {sig.hh_hl_count}, vol-ratio {sig.vol_ratio:.2f}x, OI Δ {sig.oi_change_pct_1h:+.2f}%/h")
        print(f"  5m streak {sig.streak_5m}, whale-bar vol {sig.whale_bar_vol/1e6:.1f}M")
        print(f"  ✓ {', '.join(sig.conditions_met)}")
        print(f"  ✗ {', '.join(sig.conditions_failed)}" if sig.conditions_failed else "  (all passed)")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
