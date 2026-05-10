"""Risk Engine — pure functions consumed by the Risk Manager Agent.

Responsibilities:
  1. Position sizing from a stop-distance + max-loss budget.
  2. Liquidation distance for an isolated USDT-M position.
  3. Fee-aware net profit estimation.
  4. Symbol-filter validation (PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL).
  5. End-to-end ``evaluate_proposal`` that turns a Trade Proposal
     (from the Strategy Agent) into a Risk Approval (the format spec'd in
     CLAUDE.md).

Everything here is a pure function — no I/O, no global state. Callers pass in
the already-fetched market data + spec. This makes the engine trivially
testable.

Note on liquidation:
  Binance's true liquidation price uses the maintenance-margin tier table
  (per-symbol, fetched via /fapi/v1/leverageBracket which is signed). We use a
  conservative single-tier approximation here — for small wallets we never
  approach the tier boundaries anyway. The result is an *upper bound* on the
  real liquidation distance; we err on the side of the wallet.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .symbol_filters import (
    SymbolSpec,
    round_qty,
    round_price,
    round_to_step,
    validate_order,
)

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

# Conservative single-tier maintenance margin estimates (Binance USDT-M).
# Real values are tier-based via leverageBracket; these defaults are slightly
# *higher* than the lowest tier to bake in safety. Override per-symbol if
# you have tier data later.
DEFAULT_MAINT_MARGIN_RATE = Decimal("0.005")    # 0.5 %  (small notional / low tier)

# Default Binance USDT-M futures fees (taker entry + taker exit by default —
# pessimistic). Maker fees are lower; if you can guarantee maker fills, pass
# fee_rate_per_side=0.0002.
DEFAULT_TAKER_FEE = Decimal("0.0005")          # 0.05 % per side

# Slippage budget added on top of fees. Conservative for decimal-priced tokens.
DEFAULT_SLIPPAGE_BPS = Decimal("5")            # 0.05 %


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class SizingResult:
    quantity: Decimal              # base-asset, already rounded to LOT_SIZE
    margin_usdt: Decimal           # USDT margin required at chosen leverage
    notional_usdt: Decimal         # quantity * entry_price
    leverage: int                  # final leverage chosen
    estimated_fees_usdt: Decimal   # round-trip taker fees
    estimated_slippage_usdt: Decimal
    breaches: tuple[str, ...]      # filter or sanity violations


@dataclass(frozen=True)
class LiquidationEstimate:
    liquidation_price: Decimal
    distance_pct: Decimal           # |entry - liq| / entry * 100
    is_safe: bool                   # distance >= min_required_pct
    min_required_pct: Decimal


@dataclass(frozen=True)
class ProfitEstimate:
    gross_profit_usdt: Decimal       # at first take-profit, full size
    fees_usdt: Decimal               # round-trip
    slippage_usdt: Decimal
    net_profit_usdt: Decimal
    net_profit_pct_of_margin: Decimal
    risk_reward_ratio: Decimal
    fee_to_profit_ratio: Decimal     # fees / gross profit (lower = better)
    is_meaningful: bool              # net_profit covers a sane minimum


@dataclass(frozen=True)
class RiskApproval:
    """Matches the Standard Risk Approval Format from CLAUDE.md."""

    proposal_id: str
    risk_decision: str                       # approved | rejected | reduce_size | lower_leverage | wait
    max_allowed_margin_usdt: Decimal
    max_allowed_leverage: int
    max_planned_loss_usdt: Decimal
    liquidation_distance_ok: bool
    fee_profit_ok: bool
    required_changes: tuple[str, ...]
    risk_reason: str

    # Helpful detail (not in the standard format but the orchestrator
    # logs it to data/risk-state.json):
    sizing: SizingResult | None = None
    liquidation: LiquidationEstimate | None = None
    profit: ProfitEstimate | None = None

    def to_jsonable(self) -> dict:
        d = {
            "proposal_id": self.proposal_id,
            "risk_decision": self.risk_decision,
            "max_allowed_margin_usdt": str(self.max_allowed_margin_usdt),
            "max_allowed_leverage": self.max_allowed_leverage,
            "max_planned_loss_usdt": str(self.max_planned_loss_usdt),
            "liquidation_distance_ok": self.liquidation_distance_ok,
            "fee_profit_ok": self.fee_profit_ok,
            "required_changes": list(self.required_changes),
            "risk_reason": self.risk_reason,
        }
        if self.sizing:
            d["sizing"] = {
                "quantity": str(self.sizing.quantity),
                "margin_usdt": str(self.sizing.margin_usdt),
                "notional_usdt": str(self.sizing.notional_usdt),
                "leverage": self.sizing.leverage,
                "estimated_fees_usdt": str(self.sizing.estimated_fees_usdt),
                "estimated_slippage_usdt": str(self.sizing.estimated_slippage_usdt),
                "breaches": list(self.sizing.breaches),
            }
        if self.liquidation:
            d["liquidation"] = {
                "liquidation_price": str(self.liquidation.liquidation_price),
                "distance_pct": str(self.liquidation.distance_pct),
                "is_safe": self.liquidation.is_safe,
                "min_required_pct": str(self.liquidation.min_required_pct),
            }
        if self.profit:
            d["profit"] = {
                "gross_profit_usdt": str(self.profit.gross_profit_usdt),
                "fees_usdt": str(self.profit.fees_usdt),
                "slippage_usdt": str(self.profit.slippage_usdt),
                "net_profit_usdt": str(self.profit.net_profit_usdt),
                "net_profit_pct_of_margin": str(self.profit.net_profit_pct_of_margin),
                "risk_reward_ratio": str(self.profit.risk_reward_ratio),
                "fee_to_profit_ratio": str(self.profit.fee_to_profit_ratio),
                "is_meaningful": self.profit.is_meaningful,
            }
        return d


# ----------------------------------------------------------------------------
# Sizing
# ----------------------------------------------------------------------------


def size_from_risk(
    spec: SymbolSpec,
    *,
    side: str,
    entry_price: Decimal,
    stop_price: Decimal,
    max_loss_usdt: Decimal,
    leverage: int,
    fee_rate_per_side: Decimal = DEFAULT_TAKER_FEE,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    max_margin_usdt: Decimal | None = None,
) -> SizingResult:
    """Compute the qty (and resulting margin) such that a hit stop loses no
    more than ``max_loss_usdt`` after fees & slippage.

    Math::

        loss_per_unit_at_stop = |entry - stop|                        (USDT per base unit)
        round_trip_friction = entry * (2 * fee_rate + slippage_pct)    (USDT per base unit)
        worst_case_per_unit = loss_per_unit_at_stop + round_trip_friction
        qty = max_loss_usdt / worst_case_per_unit
        notional = qty * entry
        margin = notional / leverage

    We then round qty *down* to LOT_SIZE step and re-validate.
    """
    if side not in ("LONG", "SHORT"):
        raise ValueError("side must be LONG or SHORT")
    if entry_price <= 0 or stop_price <= 0:
        return SizingResult(
            quantity=Decimal("0"), margin_usdt=Decimal("0"), notional_usdt=Decimal("0"),
            leverage=leverage, estimated_fees_usdt=Decimal("0"),
            estimated_slippage_usdt=Decimal("0"),
            breaches=("entry/stop must be positive",),
        )
    if (side == "LONG" and stop_price >= entry_price) or (side == "SHORT" and stop_price <= entry_price):
        return SizingResult(
            quantity=Decimal("0"), margin_usdt=Decimal("0"), notional_usdt=Decimal("0"),
            leverage=leverage, estimated_fees_usdt=Decimal("0"),
            estimated_slippage_usdt=Decimal("0"),
            breaches=("stop on wrong side of entry",),
        )

    loss_per_unit = abs(entry_price - stop_price)
    round_trip_friction = entry_price * (
        Decimal("2") * fee_rate_per_side + slippage_bps / Decimal("10000")
    )
    worst_case_per_unit = loss_per_unit + round_trip_friction
    if worst_case_per_unit <= 0:
        return SizingResult(
            quantity=Decimal("0"), margin_usdt=Decimal("0"), notional_usdt=Decimal("0"),
            leverage=leverage, estimated_fees_usdt=Decimal("0"),
            estimated_slippage_usdt=Decimal("0"),
            breaches=("worst_case_per_unit not positive",),
        )

    raw_qty = max_loss_usdt / worst_case_per_unit
    qty = round_qty(spec, raw_qty, mode="down")

    # If we rounded down to 0 (qty step too coarse for our wallet), return 0
    # with an explicit breach — the Risk Manager turns this into "wallet too
    # small for this symbol".
    if qty <= 0:
        return SizingResult(
            quantity=Decimal("0"), margin_usdt=Decimal("0"), notional_usdt=Decimal("0"),
            leverage=leverage, estimated_fees_usdt=Decimal("0"),
            estimated_slippage_usdt=Decimal("0"),
            breaches=(f"raw qty {raw_qty} rounds to 0 at LOT_SIZE step {spec.lot_size_filter.step_size}",),
        )

    # MIN_NOTIONAL handling — when our risk-budgeted qty produces a notional
    # below Binance's minimum (very common for small wallets on decimal-priced
    # tokens), bump qty up to the smallest qty that satisfies MIN_NOTIONAL.
    # If the bumped qty's loss-at-stop exceeds the max-loss budget, return an
    # explicit breach so the Risk Manager rejects with a clear reason rather
    # than letting Binance reject the order with -4131.
    min_notional = spec.min_notional_filter.notional
    if entry_price * qty < min_notional:
        raw_min_qty = min_notional / entry_price
        min_qty = round_qty(spec, raw_min_qty, mode="up")
        if min_qty <= 0:
            min_qty = spec.lot_size_filter.step_size  # at least one step
        loss_at_min_qty = worst_case_per_unit * min_qty
        if loss_at_min_qty <= max_loss_usdt:
            qty = min_qty
        else:
            return SizingResult(
                quantity=Decimal("0"), margin_usdt=Decimal("0"),
                notional_usdt=Decimal("0"), leverage=leverage,
                estimated_fees_usdt=Decimal("0"),
                estimated_slippage_usdt=Decimal("0"),
                breaches=(
                    f"MIN_NOTIONAL {min_notional} requires qty>={min_qty}, "
                    f"but loss-at-stop {loss_at_min_qty:.4f} > max_loss "
                    f"{max_loss_usdt:.4f} — wallet/stop combo too tight",
                ),
            )

    # Wallet cap — never let computed margin exceed max_margin_usdt. Reduce
    # qty if needed; the realized loss-at-stop will be smaller than max_loss
    # which is the safer side.
    if max_margin_usdt is not None and leverage > 0:
        max_notional = max_margin_usdt * Decimal(str(leverage))
        max_qty_from_margin = max_notional / entry_price
        max_qty_capped = round_qty(spec, max_qty_from_margin, mode="down")
        if max_qty_capped > 0 and qty > max_qty_capped:
            # Only enforce the cap if the capped qty still satisfies MIN_NOTIONAL.
            if max_qty_capped * entry_price >= spec.min_notional_filter.notional:
                qty = max_qty_capped

    notional = qty * entry_price
    margin = notional / Decimal(str(leverage)) if leverage > 0 else notional

    fees = notional * fee_rate_per_side * Decimal("2")
    slippage = notional * (slippage_bps / Decimal("10000"))

    # Validate against PRICE_FILTER / LOT_SIZE / MIN_NOTIONAL
    validation = validate_order(spec, price=entry_price, quantity=qty, is_market=False)
    breaches = tuple(validation.violations)

    return SizingResult(
        quantity=qty,
        margin_usdt=margin,
        notional_usdt=notional,
        leverage=leverage,
        estimated_fees_usdt=fees,
        estimated_slippage_usdt=slippage,
        breaches=breaches,
    )


# ----------------------------------------------------------------------------
# Liquidation
# ----------------------------------------------------------------------------


def estimate_liquidation_isolated(
    *,
    side: str,
    entry_price: Decimal,
    leverage: int,
    maint_margin_rate: Decimal = DEFAULT_MAINT_MARGIN_RATE,
    min_required_distance_pct: Decimal = Decimal("30"),
) -> LiquidationEstimate:
    """Approximate liquidation price for an isolated-margin USDT-M position.

    Single-tier formula::

        For LONG:  liq = entry * (1 - 1/L + maint_margin_rate)
        For SHORT: liq = entry * (1 + 1/L - maint_margin_rate)

    For typical small-account leverage (3x-5x) and the conservative
    maint_margin_rate default, the error vs Binance's true tiered formula is
    small and *biased toward us* (we'd report a slightly closer liquidation,
    leading us to use less leverage — that's exactly the side we want to err
    on).

    Args:
        min_required_distance_pct: how much room we demand between entry and
            liquidation. Default 30% — i.e., we refuse trades where price has
            to move 30%+ in our face just to liquidate. For 3x leverage this
            is comfortably satisfied; for 20x it isn't.
    """
    if leverage <= 0:
        raise ValueError("leverage must be > 0")
    if entry_price <= 0:
        raise ValueError("entry_price must be > 0")
    if side == "LONG":
        liq = entry_price * (Decimal("1") - Decimal("1") / Decimal(str(leverage)) + maint_margin_rate)
    elif side == "SHORT":
        liq = entry_price * (Decimal("1") + Decimal("1") / Decimal(str(leverage)) - maint_margin_rate)
    else:
        raise ValueError("side must be LONG or SHORT")

    distance_pct = abs(entry_price - liq) / entry_price * Decimal("100")
    return LiquidationEstimate(
        liquidation_price=liq,
        distance_pct=distance_pct,
        is_safe=distance_pct >= min_required_distance_pct,
        min_required_pct=min_required_distance_pct,
    )


# ----------------------------------------------------------------------------
# Fee-aware profit
# ----------------------------------------------------------------------------


def estimate_profit(
    *,
    side: str,
    entry_price: Decimal,
    take_profit_price: Decimal,
    stop_price: Decimal,
    quantity: Decimal,
    margin_usdt: Decimal,
    fee_rate_per_side: Decimal = DEFAULT_TAKER_FEE,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    min_meaningful_pct_of_margin: Decimal = Decimal("3"),
) -> ProfitEstimate:
    """Compute net profit at the first take-profit, after round-trip fees & slippage.

    ``is_meaningful`` is True when net profit ≥ ``min_meaningful_pct_of_margin``
    of the margin used. The default 3% means we refuse setups where, at the
    first TP, we'd net less than 3% of margin — small accounts can't afford to
    chase 0.5R after fees.
    """
    if side == "LONG":
        gross_per_unit = take_profit_price - entry_price
        risk_per_unit = entry_price - stop_price
    else:
        gross_per_unit = entry_price - take_profit_price
        risk_per_unit = stop_price - entry_price

    notional_entry = entry_price * quantity
    notional_exit = take_profit_price * quantity
    fees = (notional_entry + notional_exit) * fee_rate_per_side
    slippage = (notional_entry + notional_exit) * (slippage_bps / Decimal("10000"))
    gross = gross_per_unit * quantity
    net = gross - fees - slippage

    pct_of_margin = (net / margin_usdt * Decimal("100")) if margin_usdt > 0 else Decimal("0")

    rr = (gross_per_unit / risk_per_unit) if risk_per_unit > 0 else Decimal("0")
    fee_ratio = (fees / gross) if gross > 0 else Decimal("999")

    return ProfitEstimate(
        gross_profit_usdt=gross,
        fees_usdt=fees,
        slippage_usdt=slippage,
        net_profit_usdt=net,
        net_profit_pct_of_margin=pct_of_margin,
        risk_reward_ratio=rr,
        fee_to_profit_ratio=fee_ratio,
        is_meaningful=pct_of_margin >= min_meaningful_pct_of_margin and net > 0,
    )


# ----------------------------------------------------------------------------
# Top-level proposal evaluator
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskConfig:
    wallet_usdt: Decimal = Decimal("10")
    max_margin_per_trade_usdt: Decimal = Decimal("2")
    default_margin_per_trade_usdt: Decimal = Decimal("1")
    max_planned_loss_pct_of_margin: Decimal = Decimal("0.05")  # 5 %
    max_leverage: int = 5
    default_leverage: int = 3
    min_liquidation_distance_pct: Decimal = Decimal("30")
    min_meaningful_pct_of_margin: Decimal = Decimal("3")


def evaluate_proposal(
    *,
    proposal_id: str,
    spec: SymbolSpec,
    side: str,
    entry_price: Decimal,
    stop_price: Decimal,
    take_profit_price: Decimal,
    cfg: RiskConfig | None = None,
    fee_rate_per_side: Decimal = DEFAULT_TAKER_FEE,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    desired_leverage: int | None = None,
    desired_margin_usdt: Decimal | None = None,
) -> RiskApproval:
    """Top-level evaluator. Builds sizing, liquidation, profit estimates and
    returns a fully-populated RiskApproval matching CLAUDE.md.

    The outcome is decided by a small rule pyramid:

      1. Sizing breaches → rejected.
      2. Liquidation too close → rejected (caller can retry with lower leverage).
      3. Profit not meaningful (fees eat returns) → rejected.
      4. Margin > max_margin_per_trade → reduce_size.
      5. Otherwise → approved.
    """
    cfg = cfg or RiskConfig()
    leverage = desired_leverage if desired_leverage is not None else cfg.default_leverage
    leverage = max(1, min(leverage, cfg.max_leverage))

    margin_target = (
        desired_margin_usdt if desired_margin_usdt is not None else cfg.default_margin_per_trade_usdt
    )
    margin_target = min(margin_target, cfg.max_margin_per_trade_usdt)
    max_loss = margin_target * cfg.max_planned_loss_pct_of_margin

    sizing = size_from_risk(
        spec,
        side=side,
        entry_price=entry_price,
        stop_price=stop_price,
        max_loss_usdt=max_loss,
        leverage=leverage,
        fee_rate_per_side=fee_rate_per_side,
        slippage_bps=slippage_bps,
        max_margin_usdt=cfg.max_margin_per_trade_usdt,
    )

    if sizing.quantity <= 0 or sizing.breaches:
        return RiskApproval(
            proposal_id=proposal_id,
            risk_decision="rejected",
            max_allowed_margin_usdt=cfg.max_margin_per_trade_usdt,
            max_allowed_leverage=cfg.max_leverage,
            max_planned_loss_usdt=max_loss,
            liquidation_distance_ok=False,
            fee_profit_ok=False,
            required_changes=tuple(sizing.breaches) or ("could not size position",),
            risk_reason="sizing failed: " + (", ".join(sizing.breaches) if sizing.breaches else "qty rounds to 0"),
            sizing=sizing,
        )

    liq = estimate_liquidation_isolated(
        side=side,
        entry_price=entry_price,
        leverage=leverage,
        min_required_distance_pct=cfg.min_liquidation_distance_pct,
    )

    profit = estimate_profit(
        side=side,
        entry_price=entry_price,
        take_profit_price=take_profit_price,
        stop_price=stop_price,
        quantity=sizing.quantity,
        margin_usdt=sizing.margin_usdt,
        fee_rate_per_side=fee_rate_per_side,
        slippage_bps=slippage_bps,
        min_meaningful_pct_of_margin=cfg.min_meaningful_pct_of_margin,
    )

    required_changes: list[str] = []
    decision = "approved"

    if not liq.is_safe:
        decision = "lower_leverage"
        required_changes.append(
            f"liquidation distance {liq.distance_pct:.2f}% < required {liq.min_required_pct}% — reduce leverage"
        )

    if not profit.is_meaningful:
        decision = "rejected" if decision == "approved" else decision
        required_changes.append(
            f"net profit {profit.net_profit_pct_of_margin:.2f}% of margin < required "
            f"{cfg.min_meaningful_pct_of_margin}% (fees consume too much)"
        )

    if sizing.margin_usdt > cfg.max_margin_per_trade_usdt and decision == "approved":
        decision = "reduce_size"
        required_changes.append(
            f"margin {sizing.margin_usdt:.4f} > max {cfg.max_margin_per_trade_usdt} per trade"
        )

    risk_reason = (
        "approved" if decision == "approved"
        else "; ".join(required_changes) or decision
    )

    return RiskApproval(
        proposal_id=proposal_id,
        risk_decision=decision,
        max_allowed_margin_usdt=cfg.max_margin_per_trade_usdt,
        max_allowed_leverage=cfg.max_leverage,
        max_planned_loss_usdt=max_loss,
        liquidation_distance_ok=liq.is_safe,
        fee_profit_ok=profit.is_meaningful,
        required_changes=tuple(required_changes),
        risk_reason=risk_reason,
        sizing=sizing,
        liquidation=liq,
        profit=profit,
    )


__all__ = [
    "DEFAULT_MAINT_MARGIN_RATE",
    "DEFAULT_TAKER_FEE",
    "DEFAULT_SLIPPAGE_BPS",
    "SizingResult",
    "LiquidationEstimate",
    "ProfitEstimate",
    "RiskApproval",
    "RiskConfig",
    "size_from_risk",
    "estimate_liquidation_isolated",
    "estimate_profit",
    "evaluate_proposal",
]
