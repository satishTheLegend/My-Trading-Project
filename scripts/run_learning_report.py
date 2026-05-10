"""CLI: generate the Learning Agent's end-of-day report.

Usage::

    # Print the report:
    python -m scripts.run_learning_report

    # Persist insights into memory/learning-insights.md:
    python -m scripts.run_learning_report --persist

    # Only consider trades since a date:
    python -m scripts.run_learning_report --since 2026-05-01

    # Lower the statistical floor (for early days when sample size is low):
    python -m scripts.run_learning_report --floor 5
"""

from __future__ import annotations

import argparse
import json
import sys

from .learning import (
    DEFAULT_STATISTICAL_FLOOR,
    append_insights_to_memory,
    generate_report,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Aggregate journal → insights")
    p.add_argument("--since", help="ISO date/timestamp; only consider trades after this")
    p.add_argument("--floor", type=int, default=DEFAULT_STATISTICAL_FLOOR,
                   help=f"statistical floor for actionable insights (default {DEFAULT_STATISTICAL_FLOOR})")
    p.add_argument("--persist", action="store_true",
                   help="append insights to memory/learning-insights.md")
    args = p.parse_args(argv)

    report = generate_report(statistical_floor=args.floor, since_iso=args.since)
    payload = report.to_jsonable()

    if args.persist:
        appended = append_insights_to_memory(report.insights)
        payload["persisted_insights_count"] = appended

    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
