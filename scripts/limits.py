"""Pre-trade limit checker.

Pure functions. The cycle calls ``check_proposal`` BEFORE constructing an
execution plan; the router would refuse anyway, but checking here saves a
round-trip and produces a clean "rejected by limits" journal entry instead
of a router rejection that's harder to read after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from .positions_store import Position
from .safety_state import SafetyLimits, SafetyState


# ----------------------------------------------------------------------------
# Result
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class LimitCheck:
    ok: bool
    breached: tuple[str, ...]      # rule names that fired (empty if ok)
    reasons: tuple[str, ...]       # human-friendly reason per breach

    def to_jsonable(self) -> dict:
        return {
            "ok": self.ok,
            "breached": list(self.breached),
            "reasons": list(self.reasons),
        }


# ----------------------------------------------------------------------------
# Core check
# ----------------------------------------------------------------------------


def check_proposal(
    *,
    state: SafetyState,
    limits: SafetyLimits,
    proposed_symbol: str,
    open_positions: Iterable[Position],
    fired_this_cycle: int,
) -> LimitCheck:
    """Run every cap check against a single proposal.

    Returns ``LimitCheck.ok=True`` only if every gate passes.
    """
    breached: list[str] = []
    reasons: list[str] = []

    if state.trading_paused:
        breached.append("paused")
        reasons.append(state.paused_reason or "trading paused (no specific reason recorded)")

    # Daily loss already breached (defensive — record_trade_close should have
    # already paused, but this catches a stale state from a different process).
    if (
        limits.daily_loss_limit_usdt > 0
        and state.daily_pnl_usdt < 0
        and -state.daily_pnl_usdt >= limits.daily_loss_limit_usdt
    ):
        breached.append("daily_loss_limit")
        reasons.append(
            f"daily loss {-state.daily_pnl_usdt:.4f} USDT >= limit "
            f"{limits.daily_loss_limit_usdt} USDT"
        )

    if (
        limits.consecutive_loss_limit > 0
        and state.consecutive_losses >= limits.consecutive_loss_limit
    ):
        breached.append("consecutive_loss_limit")
        reasons.append(
            f"consecutive losses {state.consecutive_losses} >= limit "
            f"{limits.consecutive_loss_limit}"
        )

    open_list = [p for p in open_positions if p.is_open]
    open_count = len(open_list)
    if limits.max_open_positions and open_count >= limits.max_open_positions:
        breached.append("max_open_positions")
        reasons.append(
            f"already {open_count} open positions; cap is {limits.max_open_positions}"
        )

    if limits.no_duplicate_symbol and any(p.symbol == proposed_symbol for p in open_list):
        breached.append("no_duplicate_symbol")
        reasons.append(f"already have an open position on {proposed_symbol}")

    if (
        limits.per_cycle_trade_cap
        and fired_this_cycle >= limits.per_cycle_trade_cap
    ):
        breached.append("per_cycle_trade_cap")
        reasons.append(
            f"already fired {fired_this_cycle} trade(s) this cycle; cap is "
            f"{limits.per_cycle_trade_cap}"
        )

    return LimitCheck(ok=not breached, breached=tuple(breached), reasons=tuple(reasons))


__all__ = ["LimitCheck", "check_proposal"]
