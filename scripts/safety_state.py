"""Centralized Safety/Kill-Switch state.

This is the agency-wide single source of truth for:
  - daily realized PnL (rolls over at UTC midnight)
  - consecutive losses (resets on a winning trade)
  - currently paused? why? until when?
  - per-cycle counters (trades fired this cycle, used by limits.py)

Persistence:
  - data/risk-state.json    — counters (rolling daily/consecutive)
  - data/system-health.json — paused flag + reason exposed to other agents

Both are written atomically (temp file + os.replace) so a crash mid-update
never leaves the canonical files corrupt. The Watcher updates state on
position close. The cycle CLIs (`run_live_cycle.py`, `run_full_auto_cycle.py`)
check state before firing each trade and again between trades.

Daily rollover policy:
  - At the start of each cycle, ``perform_daily_rollover_if_needed()`` checks
    whether the stored ``daily_period_start`` is on a different UTC date
    than today. If so, archive yesterday's stats into a ``last_period`` block
    and zero out today's counters.
  - Auto-pauses don't survive rollover *unless* they're flagged
    ``carry_over_rollover``. That is reserved for hard incidents (API key
    misconfigured, withdrawal permission detected, etc.) — defaults are
    cleared on rollover so the agency can resume next day.

Pause states:
  - "ok"            — trading allowed
  - "paused"        — trading disallowed; reason in `paused_reason`
  - "cooldown"      — paused until `paused_until_iso` UTC; auto-clears on cycle

Why a separate module instead of inlining in health_check.py?
  - health_check.py is read-only (it's a probe). This file owns mutation,
    so the rule about who can flip safety state is explicit.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
RISK_STATE = _PROJECT_ROOT / "data" / "risk-state.json"
SYSTEM_HEALTH = _PROJECT_ROOT / "data" / "system-health.json"


# ----------------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class SafetyLimits:
    """The caps Phase 6 enforces. All fields are positive numbers; "loss" is
    expressed as a positive USDT amount, not negative.
    """
    wallet_usdt: Decimal = Decimal("10")
    daily_loss_limit_usdt: Decimal = Decimal("1.5")     # 15 % of 10 USDT
    consecutive_loss_limit: int = 3
    max_open_positions: int = 2
    no_duplicate_symbol: bool = True
    per_cycle_trade_cap: int = 5
    cooldown_minutes_after_consecutive_losses: int = 60


# ----------------------------------------------------------------------------
# State dataclass — what lives on disk
# ----------------------------------------------------------------------------


@dataclass
class SafetyState:
    daily_pnl_usdt: Decimal = Decimal("0")
    daily_period_start: str = ""           # ISO date of the current rolling day (UTC)
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    trades_today: int = 0
    last_trade_at: str | None = None
    trading_paused: bool = False
    paused_reason: str | None = None
    paused_at: str | None = None
    paused_until_iso: str | None = None    # set for cooldown windows
    pause_carry_over_rollover: bool = False

    # Archive of the previous day's stats for context.
    last_period: dict[str, Any] = field(default_factory=dict)

    # ------- helpers -------------------------------------------------

    @property
    def is_paused_now(self) -> bool:
        if not self.trading_paused:
            return False
        if self.paused_until_iso:
            try:
                until = dt.datetime.fromisoformat(self.paused_until_iso.replace("Z", "+00:00"))
            except ValueError:
                return True
            now = dt.datetime.utcnow().replace(tzinfo=until.tzinfo or dt.timezone.utc)
            if now >= until:
                # Cooldown elapsed; the next call to ``check_can_trade`` will
                # auto-clear. Keep paused True until then so the cycle still
                # sees the pause at this exact moment.
                return True
        return True

    @property
    def cooldown_remaining_minutes(self) -> float | None:
        if not self.paused_until_iso:
            return None
        try:
            until = dt.datetime.fromisoformat(self.paused_until_iso.replace("Z", "+00:00"))
        except ValueError:
            return None
        now = dt.datetime.utcnow().replace(tzinfo=until.tzinfo or dt.timezone.utc)
        delta_s = (until - now).total_seconds()
        return max(0.0, delta_s / 60.0)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "daily_pnl_usdt": str(self.daily_pnl_usdt),
            "daily_period_start": self.daily_period_start,
            "consecutive_losses": self.consecutive_losses,
            "consecutive_wins": self.consecutive_wins,
            "trades_today": self.trades_today,
            "last_trade_at": self.last_trade_at,
            "trading_paused": self.trading_paused,
            "paused_reason": self.paused_reason,
            "paused_at": self.paused_at,
            "paused_until_iso": self.paused_until_iso,
            "pause_carry_over_rollover": self.pause_carry_over_rollover,
            "last_period": self.last_period,
        }

    @classmethod
    def from_jsonable(cls, d: dict[str, Any]) -> "SafetyState":
        return cls(
            daily_pnl_usdt=Decimal(str(d.get("daily_pnl_usdt", "0"))),
            daily_period_start=d.get("daily_period_start", ""),
            consecutive_losses=int(d.get("consecutive_losses", 0)),
            consecutive_wins=int(d.get("consecutive_wins", 0)),
            trades_today=int(d.get("trades_today", 0)),
            last_trade_at=d.get("last_trade_at"),
            trading_paused=bool(d.get("trading_paused", False)),
            paused_reason=d.get("paused_reason"),
            paused_at=d.get("paused_at"),
            paused_until_iso=d.get("paused_until_iso"),
            pause_carry_over_rollover=bool(d.get("pause_carry_over_rollover", False)),
            last_period=d.get("last_period", {}) or {},
        )


# ----------------------------------------------------------------------------
# Manager — owns mutation
# ----------------------------------------------------------------------------


class SafetyStateManager:
    """Reads/writes the safety state files atomically. Everything goes
    through here — no other module mutates ``risk-state.json`` directly.
    """

    def __init__(
        self,
        *,
        risk_state_path: Path | None = None,
        system_health_path: Path | None = None,
        limits: SafetyLimits | None = None,
    ) -> None:
        self.risk_state_path = risk_state_path or RISK_STATE
        self.system_health_path = system_health_path or SYSTEM_HEALTH
        self.limits = limits or SafetyLimits()

    # ----- read --------------------------------------------------------

    def load(self) -> SafetyState:
        d = self._read_json(self.risk_state_path)
        return SafetyState.from_jsonable(d) if d else SafetyState()

    # ----- write -------------------------------------------------------

    def save(self, state: SafetyState) -> None:
        self._atomic_write(self.risk_state_path, json.dumps(state.to_jsonable(), indent=2))
        # Mirror the user-facing pieces into system-health.json so other
        # agents (health_check, position_manager) can see them without
        # importing safety_state.
        sys = self._read_json(self.system_health_path) or {}
        sys.update({
            "trading_paused": state.trading_paused,
            "paused_reason": state.paused_reason,
            "consecutive_losses": state.consecutive_losses,
            "daily_pnl_usdt": float(state.daily_pnl_usdt),
            "wallet_threshold_ok": True,    # populated separately; default true
            "last_updated": _now_iso(),
        })
        self._atomic_write(self.system_health_path, json.dumps(sys, indent=2))

    # ----- transitions -----------------------------------------------

    def perform_daily_rollover_if_needed(self, state: SafetyState | None = None) -> tuple[SafetyState, bool]:
        """If ``state.daily_period_start`` is on a previous UTC date, archive
        and reset. Returns (state, did_rollover)."""
        state = state or self.load()
        today_utc = dt.datetime.utcnow().date().isoformat()
        if state.daily_period_start == today_utc:
            return state, False

        # Archive yesterday's stats.
        if state.daily_period_start:
            state.last_period = {
                "period_start": state.daily_period_start,
                "daily_pnl_usdt": str(state.daily_pnl_usdt),
                "trades_count": state.trades_today,
                "ending_consecutive_losses": state.consecutive_losses,
            }

        state.daily_period_start = today_utc
        state.daily_pnl_usdt = Decimal("0")
        state.trades_today = 0
        # Consecutive-loss counter persists across rollover — losing 3 in a
        # row is meaningful even if midnight passes.

        # Auto-clear pauses unless flagged carry-over.
        if state.trading_paused and not state.pause_carry_over_rollover:
            state.trading_paused = False
            state.paused_reason = None
            state.paused_at = None
            state.paused_until_iso = None

        self.save(state)
        return state, True

    def record_trade_close(
        self, *, net_pnl_usdt: Decimal, symbol: str | None = None,
    ) -> SafetyState:
        """Called by the watcher each time a position closes. Updates daily
        PnL + consecutive counters + auto-pauses if a limit is breached."""
        state = self.load()
        state, _ = self.perform_daily_rollover_if_needed(state)

        state.daily_pnl_usdt += net_pnl_usdt
        state.last_trade_at = _now_iso()
        state.trades_today += 1

        if net_pnl_usdt > 0:
            state.consecutive_wins += 1
            state.consecutive_losses = 0
        elif net_pnl_usdt < 0:
            state.consecutive_losses += 1
            state.consecutive_wins = 0
        # Zero PnL: rare (paper-only); leave counters unchanged.

        # Breach checks
        breach_reason = self._compute_breach(state)
        if breach_reason and not state.trading_paused:
            state.trading_paused = True
            state.paused_reason = breach_reason
            state.paused_at = _now_iso()
            # Only consecutive-loss breaches get a cooldown window; daily-loss
            # breaches stay until the daily rollover (or manual resume).
            if "consecutive" in breach_reason and self.limits.cooldown_minutes_after_consecutive_losses > 0:
                until = dt.datetime.utcnow() + dt.timedelta(
                    minutes=self.limits.cooldown_minutes_after_consecutive_losses
                )
                state.paused_until_iso = until.isoformat(timespec="seconds") + "Z"

        self.save(state)
        return state

    def pause(self, reason: str, *, carry_over_rollover: bool = False,
              until_minutes: float | None = None) -> SafetyState:
        state = self.load()
        state.trading_paused = True
        state.paused_reason = reason
        state.paused_at = _now_iso()
        state.pause_carry_over_rollover = carry_over_rollover
        if until_minutes:
            until = dt.datetime.utcnow() + dt.timedelta(minutes=until_minutes)
            state.paused_until_iso = until.isoformat(timespec="seconds") + "Z"
        else:
            state.paused_until_iso = None
        self.save(state)
        return state

    def resume(self, *, manual: bool = True) -> SafetyState:
        state = self.load()
        state.trading_paused = False
        state.paused_reason = None
        state.paused_at = None
        state.paused_until_iso = None
        state.pause_carry_over_rollover = False
        self.save(state)
        return state

    def reset_daily_counters(self) -> SafetyState:
        """Force a daily reset (manual rollover). Useful after a bad day to
        let the user start fresh without waiting for UTC midnight."""
        state = self.load()
        state.daily_period_start = ""    # makes the next rollover fire
        state, _ = self.perform_daily_rollover_if_needed(state)
        return state

    # ----- inspection --------------------------------------------------

    def check_can_trade(self, *, force_rollover_check: bool = True) -> tuple[SafetyState, bool, str]:
        """Returns (state, can_trade, reason). Auto-clears expired cooldowns."""
        state = self.load()
        if force_rollover_check:
            state, _ = self.perform_daily_rollover_if_needed(state)
        if state.trading_paused:
            # Check cooldown expiry.
            if state.paused_until_iso:
                try:
                    until = dt.datetime.fromisoformat(state.paused_until_iso.replace("Z", "+00:00"))
                    now = dt.datetime.utcnow().replace(tzinfo=until.tzinfo or dt.timezone.utc)
                    if now >= until:
                        # Cooldown over → auto-resume.
                        state.trading_paused = False
                        state.paused_reason = None
                        state.paused_at = None
                        state.paused_until_iso = None
                        self.save(state)
                        return state, True, "cooldown elapsed; trading allowed"
                except ValueError:
                    pass
            return state, False, state.paused_reason or "trading paused"
        return state, True, "ok"

    # ----- internals --------------------------------------------------

    def _compute_breach(self, state: SafetyState) -> str | None:
        # Daily loss breach. ``daily_pnl_usdt`` is signed (negative = loss).
        if (
            self.limits.daily_loss_limit_usdt > 0
            and state.daily_pnl_usdt < 0
            and -state.daily_pnl_usdt >= self.limits.daily_loss_limit_usdt
        ):
            return (
                f"daily loss {-state.daily_pnl_usdt:.4f} USDT >= limit "
                f"{self.limits.daily_loss_limit_usdt} USDT"
            )
        if (
            self.limits.consecutive_loss_limit > 0
            and state.consecutive_losses >= self.limits.consecutive_loss_limit
        ):
            return (
                f"consecutive losses {state.consecutive_losses} >= limit "
                f"{self.limits.consecutive_loss_limit}"
            )
        return None

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".tmp.", delete=False,
        ) as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, path)


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


__all__ = [
    "SafetyLimits",
    "SafetyState",
    "SafetyStateManager",
    "RISK_STATE",
    "SYSTEM_HEALTH",
]
