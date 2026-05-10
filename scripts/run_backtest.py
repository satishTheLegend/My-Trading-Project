"""CLI: walk-forward backtest a single symbol.

Usage::

    # Backtest DOGEUSDT on 1h, last 500 bars (~3 weeks):
    python -m scripts.run_backtest --symbol DOGEUSDT

    # Tighter — last 200 4h bars (~33 days):
    python -m scripts.run_backtest --symbol DOGEUSDT --interval 4h --bars 200

    # Print full per-trade list:
    python -m scripts.run_backtest --symbol DOGEUSDT --verbose-trades
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from decimal import Decimal

from .backtester import backtest_symbol
from .binance_client import BinanceClient
from .market_data import MarketData
from .symbol_filters import parse_exchange_info


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Walk-forward backtest")
    p.add_argument("--symbol", required=True, help="e.g. DOGEUSDT")
    p.add_argument("--interval", default="1h",
                   choices=("5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"))
    p.add_argument("--bars", type=int, default=500)
    p.add_argument("--warmup", type=int, default=100)
    p.add_argument("--verbose-trades", action="store_true",
                   help="emit the per-trade list in the JSON output")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    market = MarketData(BinanceClient())
    info = market.get_exchange_info()
    specs = parse_exchange_info(info)
    if args.symbol not in specs:
        print(json.dumps({"error": f"unknown symbol {args.symbol}"}))
        return 1
    spec = specs[args.symbol]

    result = backtest_symbol(
        market, spec,
        interval=args.interval,
        lookback_bars=args.bars,
        warmup_bars=args.warmup,
    )

    out = result.to_jsonable()
    if not args.verbose_trades:
        # Aggregate-only output by default; full trade list is verbose.
        out["trades_sample"] = out["trades"][:5]
        out.pop("trades")

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
