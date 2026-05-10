"""Mode manager.

Resolves the effective runtime mode given env state:

    requested mode (env MODE)        →   paper | live
    allow_live_execution (env)       →   true / false
    has Binance credentials          →   true / false
    has Telegram credentials         →   true / false  (only matters if confirmation required)

Effective mode lattice::

    paper                                       — never trade live
    live-readiness-only                         — checks pass partially, no orders
    live-enabled                                — full chain green, orders allowed

`scripts/run_live_cycle.py` and `scripts/run_full_auto_cycle.py` call
``resolve_mode`` at start. Cycle CLIs that don't recognise ``live-enabled``
must default to no-execute behaviour.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .env_loader import RuntimeEnv, load_env

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODE_STATE = _PROJECT_ROOT / "data" / "mode-state.json"


EFFECTIVE_PAPER = "paper"
EFFECTIVE_LIVE_READINESS_ONLY = "live-readiness-only"
EFFECTIVE_LIVE_ENABLED = "live-enabled"


@dataclass(frozen=True)
class ModeResolution:
    requested_mode: str                  # paper | live
    effective_mode: str                  # paper | live-readiness-only | live-enabled
    live_execution_allowed: bool
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]            # human-friendly reasons live wasn't enabled
    resolved_at: str

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "requested_mode": self.requested_mode,
            "effective_mode": self.effective_mode,
            "live_execution_allowed": self.live_execution_allowed,
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
            "resolved_at": self.resolved_at,
        }


def resolve_mode(env: RuntimeEnv | None = None) -> ModeResolution:
    env = env or load_env()
    warnings: list[str] = []
    blockers: list[str] = []

    requested = env.mode
    if requested != "live":
        return ModeResolution(
            requested_mode=requested,
            effective_mode=EFFECTIVE_PAPER,
            live_execution_allowed=False,
            warnings=tuple(warnings),
            blockers=tuple(blockers),
            resolved_at=_now_iso(),
        )

    # MODE=live — gather blockers.
    if not env.allow_live_execution:
        blockers.append("ALLOW_LIVE_EXECUTION=false")
    if not env.has_binance_credentials:
        blockers.append("BINANCE_API_KEY / BINANCE_API_SECRET missing")
    if env.require_telegram_confirmation_for_live_order and not env.has_telegram_credentials:
        blockers.append(
            "REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER=true but Telegram credentials missing"
        )

    if not blockers:
        effective = EFFECTIVE_LIVE_ENABLED
        live_ok = True
    else:
        effective = EFFECTIVE_LIVE_READINESS_ONLY
        live_ok = False
        warnings.append(
            "MODE=live but live execution blocked; running live-readiness-only mode"
        )

    return ModeResolution(
        requested_mode=requested,
        effective_mode=effective,
        live_execution_allowed=live_ok,
        warnings=tuple(warnings),
        blockers=tuple(blockers),
        resolved_at=_now_iso(),
    )


def persist(resolution: ModeResolution) -> None:
    MODE_STATE.parent.mkdir(parents=True, exist_ok=True)
    MODE_STATE.write_text(json.dumps(resolution.to_jsonable(), indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Show or set the agency runtime mode")
    p.add_argument("--status", action="store_true", help="resolve and print effective mode")
    p.add_argument("--set", choices=("paper", "live"),
                   help="set MODE in data/mode-state.json (env still wins on next run)")
    args = p.parse_args(argv)

    env = load_env()
    resolution = resolve_mode(env)

    if args.set:
        # We don't actually modify env vars (env-only is the rule). We persist
        # the requested mode into mode-state.json so other tooling can see it.
        persist(ModeResolution(
            requested_mode=args.set,
            effective_mode=resolution.effective_mode if args.set == env.mode else (
                EFFECTIVE_PAPER if args.set == "paper" else EFFECTIVE_LIVE_READINESS_ONLY
            ),
            live_execution_allowed=resolution.live_execution_allowed and args.set == "live",
            warnings=(
                f"MODE env var is still {env.mode!r}; export MODE={args.set} for it to actually take effect.",
            ) if args.set != env.mode else resolution.warnings,
            blockers=resolution.blockers,
            resolved_at=_now_iso(),
        ))

    persist(resolution)
    print(json.dumps(resolution.to_jsonable(), indent=2, default=str))
    return 0


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


__all__ = [
    "ModeResolution",
    "resolve_mode",
    "persist",
    "EFFECTIVE_PAPER",
    "EFFECTIVE_LIVE_READINESS_ONLY",
    "EFFECTIVE_LIVE_ENABLED",
    "MODE_STATE",
]


if __name__ == "__main__":
    sys.exit(main())
