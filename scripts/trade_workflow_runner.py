"""Trade-workflow runner — unified entrypoint that picks the right cycle CLI
based on the resolved mode.

Usage::

    python -m scripts.trade_workflow_runner [--top N] [--save] [extra args...]

The runner:
  1. Resolves the effective mode via `scripts/mode_manager.py`.
  2. Routes to the matching cycle:
       paper                  → scripts.run_paper_cycle
       live-readiness-only    → scripts.run_paper_cycle (with --save off)
                                + a one-time live-readiness probe
       live-enabled (semi)    → scripts.run_live_cycle
       live-enabled (full)    → scripts.run_full_auto_cycle
  3. The "semi vs full" choice is controlled by the ``--auto`` flag. By default
     `live-enabled` runs as semi-auto for safety; pass ``--auto`` to opt into
     full-auto (still requires the dedicated `--i-understand-this-fires-trades-without-asking`
     confirmation flag the underlying CLI enforces).

This is a convenience wrapper. The individual cycle CLIs remain the source of
truth — pass ``--help`` to any of them for the full flag set.
"""

from __future__ import annotations

import argparse
import json
import sys

from .mode_manager import (
    EFFECTIVE_LIVE_ENABLED,
    EFFECTIVE_LIVE_READINESS_ONLY,
    EFFECTIVE_PAPER,
    resolve_mode,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Resolve mode and dispatch to the appropriate cycle runner",
        add_help=True,
    )
    p.add_argument("--auto", action="store_true",
                   help="prefer FULL_AUTO_LIVE over SEMI_AUTO_LIVE when live-enabled")
    p.add_argument("--dry-run", action="store_true",
                   help="just print which cycle would run; don't execute it")
    args, passthrough = p.parse_known_args(argv)

    resolution = resolve_mode()

    if resolution.effective_mode == EFFECTIVE_PAPER:
        target = "scripts.run_paper_cycle"
    elif resolution.effective_mode == EFFECTIVE_LIVE_READINESS_ONLY:
        target = "scripts.run_paper_cycle"
        # Surface readiness blockers to stderr but still run the paper cycle.
        sys.stderr.write(
            f"[runner] MODE=live but blocked by: {', '.join(resolution.blockers)}\n"
            "[runner] Falling back to paper cycle.\n"
        )
    elif resolution.effective_mode == EFFECTIVE_LIVE_ENABLED:
        target = "scripts.run_full_auto_cycle" if args.auto else "scripts.run_live_cycle"
    else:
        sys.stderr.write(f"[runner] unknown effective mode {resolution.effective_mode}\n")
        return 1

    if args.dry_run:
        print(json.dumps({
            "would_run": target,
            "passthrough_args": passthrough,
            "resolution": resolution.to_jsonable(),
        }, indent=2))
        return 0

    # Dispatch by importing the module and calling its main(argv).
    import importlib
    mod = importlib.import_module(target)
    return mod.main(passthrough) if hasattr(mod, "main") else 1


if __name__ == "__main__":
    sys.exit(main())
