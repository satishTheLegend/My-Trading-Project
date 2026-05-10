"""CLI: single watcher tick — what /monitor-open-positions invokes.

Loads open paper positions, applies exit logic for each, persists results,
journals closed trades.

Usage::

    # One pass over all open positions:
    python -m scripts.run_watch_positions

    # Loop with 60s sleep between ticks:
    python -m scripts.run_watch_positions --loop --interval 60

    # Force emergency exit on every position (Safety Agent override):
    python -m scripts.run_watch_positions --emergency
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime

from .binance_client import BinanceClient
from .market_data import MarketData
from .positions_store import PositionsStore
from .watcher import watch_open_positions


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run a watcher tick over open paper positions")
    p.add_argument("--loop", action="store_true", help="loop until Ctrl-C")
    p.add_argument("--interval", type=int, default=60, help="loop interval in seconds")
    p.add_argument("--emergency", action="store_true",
                   help="treat as Safety Agent emergency — close all positions this tick")
    p.add_argument("--candle-interval", default="1m",
                   help="kline interval used for monitoring (default 1m)")
    p.add_argument("--candle-lookback", type=int, default=30,
                   help="candles fetched per symbol (default 30)")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    client = BinanceClient()
    market = MarketData(client)
    store = PositionsStore()

    def tick() -> dict:
        report = watch_open_positions(
            market,
            store=store,
            candle_interval=args.candle_interval,
            candle_lookback=args.candle_lookback,
            safety_emergency=args.emergency,
        )
        return {
            "tick_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            **report.to_jsonable(),
        }

    if not args.loop:
        out = tick()
        print(json.dumps(out, indent=2, default=str))
        return 0

    try:
        while True:
            out = tick()
            print(json.dumps(out, indent=2, default=str))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
