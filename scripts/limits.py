"""Pre-trade limit checker.

Pure functions. The cycle calls ``check_proposal`` BEFORE constructing an
execution plan; the router would refuse anyway, but checking here saves a
round-trip and produces a clean "rejected by limits" journal entry instead
of a router rejection that's harder to read after the fact.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from .positions_store import Position
from .safety_state import SafetyLimits, SafetyState


# ----------------------------------------------------------------------------
# Re-entry cooldown (ENH-2026-05-11T16:55Z)
# ----------------------------------------------------------------------------
# Same-symbol re-entries on the same trading session have a documented bad
# record: 6 trades, 5 losses, 1 win, net −0.62 USDT in a single day. After a
# stop-out the structure that just triggered the SL is usually still active
# for the next 1-3 hours; after a take-profit the move has just played out
# and the next entry is most often a chase. Block both with separate windows.

_LOSS_EXIT_REASONS = frozenset({
    "stop_loss",
    "sl_hit",                       # historical exit-reason string used by exit_simulator
    "loss_research_exit",
    "sl_trail_locked",
    "sl_hit_breakeven_locked",      # locked-BE stop that ultimately closed flat-to-slight-loss
})
_PROFIT_EXIT_REASONS = frozenset({
    "take_profit",
    "tp_hit",
    "mfe_pullback_exit",
    "giveback_protection_exit",
    "quick_profit_exit",
    "floor_exit_user_rule",
})

REENTRY_COOLDOWN_AFTER_LOSS_MINUTES = 180
REENTRY_COOLDOWN_AFTER_PROFIT_MINUTES = 30


def _parse_iso_z(ts: str | None) -> dt.datetime | None:
    """Parse the project's ISO-Z timestamp format (e.g. ``2026-05-11T13:52:07Z``).

    Returns ``None`` for missing / unparseable input — callers must treat
    ``None`` as "no cooldown information" and fall through to other rules.
    """
    if not ts or not isinstance(ts, str):
        return None
    try:
        # ``fromisoformat`` accepts ``+00:00`` but not the trailing ``Z`` until
        # 3.11; normalise to be safe across runtime versions.
        norm = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        return dt.datetime.fromisoformat(norm)
    except ValueError:
        return None


def _check_recent_close_cooldown(
    symbol: str,
    recently_closed_positions: Iterable[Position],
    *,
    now: dt.datetime | None = None,
) -> tuple[bool, str]:
    """Return ``(allowed, reason)`` based on the most recent closed position.

    ``allowed=True`` and ``reason=""`` when no cooldown applies. ``allowed=False``
    with a human-readable reason when the symbol is still in cooldown after
    its most recent close.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)

    most_recent: Position | None = None
    most_recent_dt: dt.datetime | None = None
    for p in recently_closed_positions:
        if p.symbol != symbol:
            continue
        if p.is_open:
            continue
        closed_at = _parse_iso_z(p.closed_at)
        if closed_at is None:
            continue
        if closed_at.tzinfo is None:
            closed_at = closed_at.replace(tzinfo=dt.timezone.utc)
        if most_recent_dt is None or closed_at > most_recent_dt:
            most_recent = p
            most_recent_dt = closed_at

    if most_recent is None or most_recent_dt is None:
        return True, ""

    reason_tag = (most_recent.exit_reason or "").strip()
    if reason_tag in _LOSS_EXIT_REASONS:
        window = REENTRY_COOLDOWN_AFTER_LOSS_MINUTES
    elif reason_tag in _PROFIT_EXIT_REASONS:
        window = REENTRY_COOLDOWN_AFTER_PROFIT_MINUTES
    else:
        # Unknown / manual / reconciliation exits do not trip the cooldown —
        # only the documented exit kinds count.
        return True, ""

    elapsed_minutes = (now - most_recent_dt).total_seconds() / 60.0
    if elapsed_minutes >= window:
        return True, ""

    minutes_remaining = int(round(window - elapsed_minutes))
    return False, (
        f"same-symbol re-entry cooldown ({minutes_remaining} min remaining "
        f"after {reason_tag})"
    )


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
    recently_closed_positions: Iterable[Position] | None = None,
) -> LimitCheck:
    """Run every cap check against a single proposal.

    Returns ``LimitCheck.ok=True`` only if every gate passes.

    ``recently_closed_positions`` is optional for back-compat with older
    callers; when provided, the same-symbol re-entry cooldown rule is also
    enforced (ENH-2026-05-11T16:55Z).
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

    # Same-symbol re-entry cooldown after a recent close. Only enforced when
    # the caller supplied the closed-position history — keeps older callers
    # back-compatible.
    if recently_closed_positions is not None:
        allowed, cooldown_reason = _check_recent_close_cooldown(
            proposed_symbol, recently_closed_positions,
        )
        if not allowed:
            breached.append("reentry_cooldown")
            reasons.append(cooldown_reason)

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


__all__ = [
    "LimitCheck",
    "check_proposal",
    "REENTRY_COOLDOWN_AFTER_LOSS_MINUTES",
    "REENTRY_COOLDOWN_AFTER_PROFIT_MINUTES",
]
