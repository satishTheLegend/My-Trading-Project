"""CLI: one reconciliation tick. Compares data/open-positions.json vs
/fapi/v2/positionRisk and reports any drift.

Usage::

    # Single reconciliation pass against testnet (default):
    python -m scripts.run_reconcile

    # On mismatch, persist trading_paused=true to data/system-health.json:
    python -m scripts.run_reconcile --pause-on-mismatch

    # Loop every 60s (use Ctrl-C to stop):
    python -m scripts.run_reconcile --loop --interval 60
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from .account import Account
from .binance_signed_client import SignedClient
from .position_manager import reconcile_via_apis, record_health
from .positions_store import PositionsStore


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Reconcile internal vs exchange position state")
    p.add_argument("--loop", action="store_true")
    p.add_argument("--interval", type=int, default=60, help="loop interval in seconds")
    p.add_argument("--pause-on-mismatch", action="store_true",
                   help="persist trading_paused=true to data/system-health.json on mismatch")
    p.add_argument("--no-permission-check", action="store_true",
                   help="(testing) skip the permission probe before reconciling")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    client = SignedClient()
    client.enable_signed_requests()
    account = Account(client)

    if not args.no_permission_check:
        perms = account.check_permissions()
        if not perms.is_safe_to_trade:
            print(json.dumps({
                "error": "permission preflight FAILED — refusing to read account state",
                "notes": list(perms.notes),
            }, indent=2))
            return 1

    store = PositionsStore()

    def tick() -> int:
        report = reconcile_via_apis(account=account, store=store)
        if args.pause_on_mismatch:
            record_health(report, pause_on_mismatch=True)
        else:
            record_health(report, pause_on_mismatch=False)
        print(json.dumps(report.to_jsonable(), indent=2, default=str))
        return 0 if report.is_clean else 1

    if not args.loop:
        return tick()

    rc = 0
    try:
        while True:
            rc = tick()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
