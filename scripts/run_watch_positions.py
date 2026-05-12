"""CLI: single watcher tick — what /monitor-open-positions invokes.

Loads open positions, applies exit logic for each, persists results,
journals closed trades.

Usage::

    # One pass over all open positions:
    python -m scripts.run_watch_positions

    # Loop with 60s sleep between ticks:
    python -m scripts.run_watch_positions --loop --interval 60

    # Force emergency exit on every position (Safety Agent override):
    python -m scripts.run_watch_positions --emergency

    # Enable live trailing stops (requires Binance creds + signed gate):
    EXIT_TRAILING_STOP_ENABLED=true python -m scripts.run_watch_positions

Live-mode safety
----------------
By default the watcher is read-only against the exchange — it fetches public
candles and may mutate **local** state in paper mode only. In live mode it
will:
  - emit decisions for visibility,
  - refuse to flip a position to ``closed`` based on local-price comparison,
  - refuse to move the local stop_loss without first cancel-and-replacing the
    exchange algoOrder (only attempted when EXIT_TRAILING_STOP_ENABLED=true
    AND credentials are available).

Pre-tick guardrail
------------------
When credentials are present, the CLI also fetches the latest exchange
position snapshot and hands it to the watcher so any local-open / exchange-
flat divergence raises a SAFETY warning on this tick (instead of silently
desyncing).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

from .binance_client import BinanceClient
from .market_data import MarketData
from .positions_store import PositionsStore
from .watcher import watch_open_positions


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run a watcher tick over open positions")
    p.add_argument("--loop", action="store_true", help="loop until Ctrl-C")
    p.add_argument("--interval", type=int, default=60, help="loop interval in seconds")
    p.add_argument("--emergency", action="store_true",
                   help="treat as Safety Agent emergency — close all positions this tick")
    p.add_argument("--candle-interval", default="1m",
                   help="kline interval used for monitoring (default 1m)")
    p.add_argument("--candle-lookback", type=int, default=30,
                   help="candles fetched per symbol (default 30)")
    p.add_argument("--no-exchange-guardrail", action="store_true",
                   help="skip the pre-tick exchange-position snapshot "
                        "(default: fetch when credentials are available)")
    p.add_argument("--enable-trailing", action="store_true",
                   help="force-enable trailing stops this run (default: read "
                        "EXIT_TRAILING_STOP_ENABLED env var)")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    client = BinanceClient()
    market = MarketData(client)
    store = PositionsStore()

    # Pre-fetch the exchange-position snapshot only when credentials are
    # available AND the operator hasn't opted out. Failure to fetch is
    # non-fatal — the watcher falls back to local-only behavior with no
    # exchange-divergence checks.
    def _maybe_fetch_exchange_positions():
        if args.no_exchange_guardrail:
            return None
        if not os.environ.get("BINANCE_API_KEY") or not os.environ.get("BINANCE_API_SECRET"):
            return None
        try:
            from .account import Account
            from .binance_signed_client import SignedClient
            signed = SignedClient()
            signed.enable_signed_requests()
            acct = Account(signed)
            return acct.get_open_positions()
        except Exception as e:
            logging.getLogger(__name__).warning(
                "exchange-position guardrail skipped: %r", e,
            )
            return None

    # Build the trailing toggle. CLI flag wins over env var; otherwise the
    # watcher reads the env var itself.
    enable_trailing = True if args.enable_trailing else None

    def tick() -> dict:
        exch_positions = _maybe_fetch_exchange_positions()
        report = watch_open_positions(
            market,
            store=store,
            candle_interval=args.candle_interval,
            candle_lookback=args.candle_lookback,
            safety_emergency=args.emergency,
            exchange_positions=exch_positions,
            enable_trailing=enable_trailing,
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
