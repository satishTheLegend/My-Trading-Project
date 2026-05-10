"""Approval policy — pure rules deciding when a trade needs the user's
explicit OK before it can fire.

User rule (Phase 5):
    SEMI_AUTO_LIVE auto-fires if notional ≤ $50. Anything > $50 needs
    explicit user approval.

Additional defensive rules layered on top:
    - The first live trade of a session ALWAYS requires approval, regardless
      of notional. Catches typos in env vars / new symbols on day one.
    - Any trade that would push the daily loss past 75 % of the daily limit
      requires approval, even if notional is small.
    - Leverage > the user's default still fires through, but with the policy
      flagged "high_leverage" so the journal records the heuristic.

The Risk Manager has already approved the proposal by the time this module
runs — approval policy is a separate, user-facing gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalPolicy:
    """Per-mode + per-trade approval rules.

    Defaults match the user's Phase 5 instruction: $50 notional threshold.
    """
    notional_threshold_usdt: Decimal = Decimal("50")
    require_approval_for_first_trade_of_session: bool = True
    daily_loss_consumption_threshold_pct: Decimal = Decimal("75")
    flag_high_leverage_above: int = 5


# ----------------------------------------------------------------------------
# Decision
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalDecision:
    requires_user_approval: bool
    reason: str                          # short summary; goes into the journal
    triggered_rules: tuple[str, ...]     # all rules that fired (may be empty if auto)

    def to_jsonable(self) -> dict:
        return {
            "requires_user_approval": self.requires_user_approval,
            "reason": self.reason,
            "triggered_rules": list(self.triggered_rules),
        }


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------


def evaluate(
    *,
    mode: str,
    notional_usdt: Decimal,
    leverage: int,
    daily_pnl_usdt: Decimal,
    daily_loss_limit_usdt: Decimal,
    is_first_live_trade_of_session: bool,
    policy: ApprovalPolicy | None = None,
) -> ApprovalDecision:
    """Single decision point. Pure function.

    Args:
        mode: PAPER_TRADING | SEMI_AUTO_LIVE | FULL_AUTO_LIVE
        notional_usdt: total order notional (price × qty), in USDT
        leverage: chosen leverage for the trade
        daily_pnl_usdt: cumulative realised PnL today (negative = loss)
        daily_loss_limit_usdt: positive number, e.g. 1.5 for a 10-USDT wallet
            with a 15 % daily loss cap
        is_first_live_trade_of_session: True until the first live execution
            of the current process lifetime
        policy: override defaults

    Returns:
        ApprovalDecision. The orchestrator either fires immediately
        (requires_user_approval=False) or queues for the Approvals CLI.
    """
    pol = policy or ApprovalPolicy()

    # PAPER_TRADING: never gate. Caller still records the would-be decision,
    # but no human prompt fires.
    if mode == "PAPER_TRADING":
        return ApprovalDecision(
            requires_user_approval=False,
            reason="paper trading — no real money at risk",
            triggered_rules=tuple(),
        )

    # FULL_AUTO_LIVE: never gate (Phase 6 concept; kept for completeness so
    # the router has a single chokepoint).
    if mode == "FULL_AUTO_LIVE":
        return ApprovalDecision(
            requires_user_approval=False,
            reason="full-auto live — approval handled by upstream config",
            triggered_rules=tuple(),
        )

    # SEMI_AUTO_LIVE — apply the rule pyramid.
    triggered: list[str] = []
    why: list[str] = []

    if notional_usdt > pol.notional_threshold_usdt:
        triggered.append("notional_above_threshold")
        why.append(
            f"notional {notional_usdt:.4f} USDT > threshold {pol.notional_threshold_usdt} USDT"
        )

    if is_first_live_trade_of_session:
        triggered.append("first_live_trade_of_session")
        why.append("first live trade of this process lifetime")

    # Daily-loss consumption gate. Only meaningful if the limit is set
    # and the user has actually lost money today.
    if daily_loss_limit_usdt > 0 and daily_pnl_usdt < 0:
        loss_so_far = -daily_pnl_usdt
        consumption_pct = loss_so_far / daily_loss_limit_usdt * Decimal("100")
        if consumption_pct >= pol.daily_loss_consumption_threshold_pct:
            triggered.append("daily_loss_consumption_high")
            why.append(
                f"daily loss {loss_so_far:.4f} = {consumption_pct:.0f}% of "
                f"limit {daily_loss_limit_usdt} (≥ {pol.daily_loss_consumption_threshold_pct}%)"
            )

    if leverage > pol.flag_high_leverage_above:
        triggered.append("high_leverage_flag")
        why.append(
            f"leverage {leverage}x > {pol.flag_high_leverage_above}x — flagged but "
            f"does not by itself trigger approval"
        )

    requires_approval = bool({
        "notional_above_threshold",
        "first_live_trade_of_session",
        "daily_loss_consumption_high",
    } & set(triggered))

    if requires_approval:
        reason = "; ".join(why)
    else:
        reason = (
            f"auto-approve: notional {notional_usdt:.4f} ≤ "
            f"{pol.notional_threshold_usdt} threshold and no defensive rule fired"
        )

    return ApprovalDecision(
        requires_user_approval=requires_approval,
        reason=reason,
        triggered_rules=tuple(triggered),
    )


__all__ = [
    "ApprovalPolicy",
    "ApprovalDecision",
    "evaluate",
]
