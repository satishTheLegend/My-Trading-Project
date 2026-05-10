"""CLI: manage SafetyState (Phase 6).

Usage::

    # Show current state:
    python -m scripts.run_safety_reset --status

    # Resume after a safety pause (e.g. you've checked the pair manually):
    python -m scripts.run_safety_reset --resume --reason "checked manually, BTC stable"

    # Force a daily reset (zero counters, archive yesterday):
    python -m scripts.run_safety_reset --reset-daily

    # Manually pause trading:
    python -m scripts.run_safety_reset --pause --reason "I'm sleeping" --until-minutes 480

Every action writes a Safety Event to memory/safety-events.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from .journal_writer import append_safety_event
from .safety_state import SafetyStateManager


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SafetyState management")
    p.add_argument("--status", action="store_true", help="show current safety state")
    p.add_argument("--resume", action="store_true", help="clear pause + resume trading")
    p.add_argument("--reset-daily", action="store_true",
                   help="force daily rollover (zero counters)")
    p.add_argument("--pause", action="store_true", help="manually pause trading")
    p.add_argument("--reason", default="", help="reason for --pause / --resume")
    p.add_argument("--until-minutes", type=float, default=None,
                   help="optional cooldown window for --pause")
    p.add_argument("--carry-over-rollover", action="store_true",
                   help="with --pause, persist across daily rollover")
    args = p.parse_args(argv)

    safety = SafetyStateManager()
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    if args.status:
        state = safety.load()
        out = state.to_jsonable()
        out["cooldown_remaining_minutes"] = state.cooldown_remaining_minutes
        print(json.dumps(out, indent=2, default=str))
        return 0

    if args.reset_daily:
        before = safety.load()
        state = safety.reset_daily_counters()
        append_safety_event({
            "timestamp": now, "mode": "ANY",
            "event_type": "manual_daily_reset",
            "triggered_by": "user",
            "details": (
                f"forced daily rollover; previous day daily_pnl={before.daily_pnl_usdt} "
                f"trades={before.trades_today}"
            ),
            "positions_affected": [],
            "action_taken": "daily counters zeroed; pause cleared if not carry-over",
            "duration_minutes": 0,
            "resolved_at": now,
            "resolution_notes": "run_safety_reset --reset-daily",
        })
        print(json.dumps({"status": "reset", "state": state.to_jsonable()},
                         indent=2, default=str))
        return 0

    if args.resume:
        state = safety.resume(manual=True)
        append_safety_event({
            "timestamp": now, "mode": "ANY",
            "event_type": "manual_resume",
            "triggered_by": "user",
            "details": args.reason or "no reason given",
            "positions_affected": [],
            "action_taken": "trading paused flag cleared",
            "duration_minutes": 0,
            "resolved_at": now,
            "resolution_notes": "run_safety_reset --resume",
        })
        print(json.dumps({"status": "resumed", "state": state.to_jsonable()},
                         indent=2, default=str))
        return 0

    if args.pause:
        if not args.reason:
            print(json.dumps({"error": "--pause requires --reason"}))
            return 2
        state = safety.pause(
            args.reason,
            carry_over_rollover=args.carry_over_rollover,
            until_minutes=args.until_minutes,
        )
        append_safety_event({
            "timestamp": now, "mode": "ANY",
            "event_type": "manual_pause",
            "triggered_by": "user",
            "details": args.reason,
            "positions_affected": [],
            "action_taken": (
                f"trading paused"
                + (f" until {state.paused_until_iso}" if state.paused_until_iso else "")
            ),
            "duration_minutes": int(args.until_minutes or 0),
            "resolved_at": "",
            "resolution_notes": "run_safety_reset --pause",
        })
        print(json.dumps({"status": "paused", "state": state.to_jsonable()},
                         indent=2, default=str))
        return 0

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
