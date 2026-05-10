"""Profit protection — pure-function recommender.

Given an open `Position` + the latest `Candle`, compute a recommendation that
prioritises locking profit and exiting invalid trades. The watcher already
calls `exit_simulator.decide_from_candle`; this module is a higher-level
*advisory* layer the User Report Agent and Telegram Notifier can summarise
for the user.

Honest rules baked in (mirrors `agency/profit-protection-policy.md`):
  - Never recommend "hold for recovery" on a losing trade past invalidation.
  - Never recommend widening the stop.
  - Never recommend averaging down.
  - Always recommend cutting an invalidated trade.
  - At first TP, recommend partial + breakeven stop.
  - On strong MFE pullback, recommend tightening stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .market_data import Candle
from .positions_store import Position


# ----------------------------------------------------------------------------
# Recommendation type
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ProfitProtectionAdvice:
    action: str            # 'hold' | 'partial_take_profit' | 'tighten_stop' | 'move_breakeven' | 'exit_now'
    reason: str
    suggested_new_stop: Decimal | None
    suggested_close_qty: Decimal | None
    in_profit: bool
    pnl_pct_of_margin: Decimal       # signed
    mfe_pct_of_margin: Decimal       # max favorable excursion as % of margin
    pullback_pct_from_mfe: Decimal   # how far we've given back from MFE (positive number)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "suggested_new_stop": str(self.suggested_new_stop) if self.suggested_new_stop is not None else None,
            "suggested_close_qty": str(self.suggested_close_qty) if self.suggested_close_qty is not None else None,
            "in_profit": self.in_profit,
            "pnl_pct_of_margin": str(self.pnl_pct_of_margin),
            "mfe_pct_of_margin": str(self.mfe_pct_of_margin),
            "pullback_pct_from_mfe": str(self.pullback_pct_from_mfe),
        }


# ----------------------------------------------------------------------------
# Tunables
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ProfitProtectionConfig:
    # Move stop to breakeven once profit ≥ 1.0R (i.e. profit per unit ≥ original risk per unit).
    move_breakeven_at_r_multiple: Decimal = Decimal("1.0")

    # Recommend partial TP at 1.5R if no TP has been taken yet.
    partial_tp_at_r_multiple: Decimal = Decimal("1.5")
    partial_tp_fraction: Decimal = Decimal("0.5")

    # If MFE pulls back ≥ 50%, recommend tightening the stop (locking some of the gain).
    pullback_pct_to_tighten: Decimal = Decimal("50")

    # If MFE pulls back ≥ 75% AND price is back below entry → exit now (don't watch profit
    # turn into a loss).
    pullback_pct_to_exit_now: Decimal = Decimal("75")

    # If unrealized loss ≥ 80% of planned max loss AND structural exit (stop) is far,
    # exit now rather than wait for the stop.
    early_exit_at_loss_pct_of_max: Decimal = Decimal("80")


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------


def advise(
    pos: Position,
    candle: Candle,
    *,
    cfg: ProfitProtectionConfig | None = None,
) -> ProfitProtectionAdvice:
    cfg = cfg or ProfitProtectionConfig()

    mark = candle.close
    pnl_per_unit = (mark - pos.entry_price) if pos.side == "LONG" else (pos.entry_price - mark)
    risk_per_unit = (
        (pos.entry_price - pos.stop_loss) if pos.side == "LONG" and pos.stop_loss is not None
        else (pos.stop_loss - pos.entry_price) if pos.side == "SHORT" and pos.stop_loss is not None
        else Decimal("0")
    )
    risk_per_unit = abs(risk_per_unit)

    unreal = pnl_per_unit * pos.quantity
    pnl_pct = (unreal / pos.margin_usdt * Decimal("100")) if pos.margin_usdt > 0 else Decimal("0")

    mfe_pct = (
        pos.max_favorable_pnl / pos.margin_usdt * Decimal("100")
        if pos.margin_usdt > 0 else Decimal("0")
    )
    pullback_pct = Decimal("0")
    if pos.max_favorable_pnl > 0:
        # how far has unrealized fallen from MFE, as a % of MFE
        give_back = pos.max_favorable_pnl - unreal
        if give_back > 0:
            pullback_pct = give_back / pos.max_favorable_pnl * Decimal("100")
    pullback_pct = max(Decimal("0"), pullback_pct)

    in_profit = unreal > 0

    # Already-taken partial TP? We tag positions in exit_simulator.apply_decision.
    already_partial = any(n.startswith("partial_tp_at:") for n in pos.notes)

    # Compute "R" — multiple of original risk_per_unit we're up.
    r_multiple = pnl_per_unit / risk_per_unit if risk_per_unit > 0 else Decimal("0")

    # Rule 1: in heavy give-back from MFE AND back below entry → exit now.
    if (
        pos.max_favorable_pnl > 0
        and pullback_pct >= cfg.pullback_pct_to_exit_now
        and unreal <= 0
    ):
        return ProfitProtectionAdvice(
            action="exit_now",
            reason=(
                f"gave back {pullback_pct:.0f}% of MFE and dropped back below entry — "
                "don't let a winner become a loser"
            ),
            suggested_new_stop=None,
            suggested_close_qty=pos.quantity,
            in_profit=False,
            pnl_pct_of_margin=pnl_pct,
            mfe_pct_of_margin=mfe_pct,
            pullback_pct_from_mfe=pullback_pct,
        )

    # Rule 2: profit reached partial-TP threshold and we haven't taken one yet.
    if (
        in_profit
        and not already_partial
        and r_multiple >= cfg.partial_tp_at_r_multiple
    ):
        qty_close = (pos.quantity * cfg.partial_tp_fraction).quantize(Decimal("1"))
        if qty_close <= 0:
            qty_close = Decimal("1")
        qty_close = min(qty_close, pos.quantity)
        return ProfitProtectionAdvice(
            action="partial_take_profit",
            reason=f"profit reached {r_multiple:.2f}R — lock half and trail the rest",
            suggested_new_stop=pos.entry_price,    # breakeven
            suggested_close_qty=qty_close,
            in_profit=True,
            pnl_pct_of_margin=pnl_pct,
            mfe_pct_of_margin=mfe_pct,
            pullback_pct_from_mfe=pullback_pct,
        )

    # Rule 3: profit reached breakeven threshold but no partial yet → move stop to BE.
    if (
        in_profit
        and r_multiple >= cfg.move_breakeven_at_r_multiple
        and pos.stop_loss is not None
        and (
            (pos.side == "LONG" and pos.stop_loss < pos.entry_price)
            or (pos.side == "SHORT" and pos.stop_loss > pos.entry_price)
        )
    ):
        return ProfitProtectionAdvice(
            action="move_breakeven",
            reason=f"profit reached {r_multiple:.2f}R — eliminate downside risk",
            suggested_new_stop=pos.entry_price,
            suggested_close_qty=None,
            in_profit=True,
            pnl_pct_of_margin=pnl_pct,
            mfe_pct_of_margin=mfe_pct,
            pullback_pct_from_mfe=pullback_pct,
        )

    # Rule 4: meaningful pullback from MFE (still in profit) → tighten stop.
    if (
        pos.max_favorable_pnl > 0
        and unreal > 0
        and pullback_pct >= cfg.pullback_pct_to_tighten
    ):
        # Suggest a stop midway between current price and entry.
        if pos.side == "LONG":
            new_stop = (mark + pos.entry_price) / Decimal("2")
            improves = pos.stop_loss is None or new_stop > pos.stop_loss
        else:
            new_stop = (mark + pos.entry_price) / Decimal("2")
            improves = pos.stop_loss is None or new_stop < pos.stop_loss
        if improves:
            return ProfitProtectionAdvice(
                action="tighten_stop",
                reason=f"gave back {pullback_pct:.0f}% from MFE — protect remaining profit",
                suggested_new_stop=new_stop,
                suggested_close_qty=None,
                in_profit=True,
                pnl_pct_of_margin=pnl_pct,
                mfe_pct_of_margin=mfe_pct,
                pullback_pct_from_mfe=pullback_pct,
            )

    # Rule 5: in loss + at ≥ 80% of planned max loss → recommend exit even before stop.
    if not in_profit and pos.margin_usdt > 0:
        # Approximate planned max loss = 5% of margin (matches default risk-engine cap).
        # Caller can override by inspecting cfg / risk_engine if desired.
        planned_max_loss = pos.margin_usdt * Decimal("0.05")
        if planned_max_loss > 0 and abs(unreal) >= planned_max_loss * cfg.early_exit_at_loss_pct_of_max / Decimal("100"):
            return ProfitProtectionAdvice(
                action="exit_now",
                reason=(
                    f"unrealized loss {unreal:.4f} USDT ≥ "
                    f"{cfg.early_exit_at_loss_pct_of_max:.0f}% of planned max loss — "
                    "cut before it gets worse"
                ),
                suggested_new_stop=None,
                suggested_close_qty=pos.quantity,
                in_profit=False,
                pnl_pct_of_margin=pnl_pct,
                mfe_pct_of_margin=mfe_pct,
                pullback_pct_from_mfe=pullback_pct,
            )

    return ProfitProtectionAdvice(
        action="hold",
        reason="no profit-protection trigger fired",
        suggested_new_stop=None,
        suggested_close_qty=None,
        in_profit=in_profit,
        pnl_pct_of_margin=pnl_pct,
        mfe_pct_of_margin=mfe_pct,
        pullback_pct_from_mfe=pullback_pct,
    )


__all__ = [
    "ProfitProtectionConfig",
    "ProfitProtectionAdvice",
    "advise",
]
