"""CLI: emergency-close every open Binance Futures position. The
``/emergency-shutdown`` slash command's target.

Usage::

    # Testnet emergency close (default):
    python -m scripts.run_emergency_close --i-understand

    # Mainnet:
    BINANCE_LIVE=true python -m scripts.run_emergency_close --i-understand --reason "BTC dumped"

The ``--i-understand`` flag is mandatory — there's no recovery from a
mass-close, and we want one extra speed-bump between Ctrl-Tab and "all my
positions are gone".
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .account import Account
from .binance_signed_client import (
    SignedClient,
    SignedRequestsDisabledError,
)
from .emergency_close import emergency_close_all
from .live_execution import LiveExecution


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Emergency close all Binance Futures positions")
    p.add_argument("--i-understand", action="store_true",
                   help="confirm you want to close every open position")
    p.add_argument("--reason", default="manual emergency",
                   help="free-text reason recorded in safety-events.md")
    p.add_argument("--skip-permission-check", action="store_true",
                   help="(testing only) skip the withdrawal-permission probe")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if not args.i_understand:
        print(json.dumps({
            "error": "refusing to run without --i-understand. "
                     "This closes EVERY open futures position with a market order."
        }, indent=2))
        return 2

    client = SignedClient()
    account = Account(client)

    # Open the signed gate, then run permission preflight.
    client.enable_signed_requests()

    if not args.skip_permission_check:
        try:
            perms = account.check_permissions()
        except SignedRequestsDisabledError as e:
            print(json.dumps({"error": f"signed gate refused: {e}"}, indent=2))
            return 1
        if not perms.is_safe_to_trade:
            print(json.dumps({
                "error": "permission preflight FAILED — refusing to send orders.",
                "report": {
                    "trading_enabled": perms.trading_enabled,
                    "withdrawals_enabled": perms.withdrawals_enabled,
                    "futures_enabled": perms.futures_enabled,
                    "ip_restrict": perms.ip_restrict,
                    "notes": list(perms.notes),
                },
            }, indent=2))
            return 1

    execution = LiveExecution(client)
    try:
        report = emergency_close_all(account=account, execution=execution, reason=args.reason)
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, indent=2))
        return 1

    print(json.dumps(report.to_jsonable(), indent=2, default=str))
    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())
