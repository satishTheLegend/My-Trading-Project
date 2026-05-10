"""Exit simulator — pure-function exit decisions for a paper position.

Given a `Position` and either:
  - a fresh `Candle` (intra-bar simulation, e.g. backtester walking history), or
  - a current mark price (live paper polling),

decide one of:
  - HOLD                  — nothing to do
  - PARTIAL_TP            — first/second TP target hit, take a fraction of qty
  - FULL_TP               — final TP target hit
  - STOP_HIT              — stop-loss touched
  - TRAIL_STOP            — favorable price moved enough; tighten stop
  - MOVE_STOP_BREAKEVEN   — first TP hit; raise stop to entry
  - INVALIDATION_EXIT     — structural reason to bail (BTC danger, funding, etc.)
  - EMERGENCY_EXIT        — Safety Agent demanded close

Conservative tie-break: if a single bar's high/low spans both stop and TP,
we assume the **stop hit first**. This is the worst-case-for-trader assumption
and prevents the backtester from fooling itself with optimistic fills.

Outputs are advisory — the Watcher Agent calls into here, then routes the
decision through Execution Agent (Phase 4 live, or this module's own apply_*
helpers in paper mode).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

from .market_data import Candle
from .positions_store import Position
from .risk_engine import DEFAULT_TAKER_FEE, DEFAULT_SLIPPAGE_BPS


# ----------------------------------------------------------------------------
# Decision types
# ----------------------------------------------------------------------------

DECISION_HOLD = "hold"
DECISION_PARTIAL_TP = "partial_tp"
DECISION_FULL_TP = "full_tp"
DECISION_STOP_HIT = "stop_hit"
DECISION_TRAIL_STOP = "trail_stop"
DECISION_MOVE_STOP_BREAKEVEN = "move_stop_breakeven"
DECISION_INVALIDATION_EXIT = "invalidation_exit"
DECISION_EMERGENCY_EXIT = "emergency_exit"


@dataclass(frozen=True)
class ExitDecision:
    decision: str                       # one of DECISION_*
    reason: str
    fill_price: Decimal | None          # price at which the exit/partial fills
    qty_to_close: Decimal               # 0 if hold/move_stop only
    new_stop_loss: Decimal | None       # set when decision moves the stop
    is_terminal: bool                   # True if the position should be closed afterwards

    def to_jsonable(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "fill_price": str(self.fill_price) if self.fill_price is not None else None,
            "qty_to_close": str(self.qty_to_close),
            "new_stop_loss": str(self.new_stop_loss) if self.new_stop_loss is not None else None,
            "is_terminal": self.is_terminal,
        }


# ----------------------------------------------------------------------------
# Tunables
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ExitConfig:
    """How aggressively the exit logic protects open trades."""

    # Fraction of remaining qty closed at the first TP. The rest runs to TP2/3
    # under a trailing stop.
    partial_tp_fraction: Decimal = Decimal("0.5")

    # Once first TP fills, raise stop to entry (lock breakeven).
    move_to_breakeven_on_first_tp: bool = True

    # Trailing-stop lookback: when latest favorable candle is N×ATR ahead of
    # the stop, ratchet the stop to (price - N_keep × ATR).
    trail_atr_multiple_trigger: Decimal = Decimal("2.0")
    trail_atr_multiple_keep: Decimal = Decimal("1.2")

    # Time-based invalidation. Phase 3 keeps it simple: close if the position
    # has been open longer than max_hold_minutes AND hasn't moved in our
    # favor (MFE < min_mfe_pct_of_margin).
    max_hold_minutes: int = 24 * 60          # 24h
    min_mfe_pct_of_margin_to_keep_holding: Decimal = Decimal("3")


# ----------------------------------------------------------------------------
# Decision functions
# ----------------------------------------------------------------------------


def decide_from_candle(
    pos: Position,
    candle: Candle,
    *,
    cfg: ExitConfig | None = None,
    atr_value: Decimal | None = None,
    invalidation_reason: str | None = None,
    safety_emergency: bool = False,
) -> ExitDecision:
    """Decide what to do with ``pos`` given a single closed candle.

    Order of precedence (highest first):
      1. Safety emergency
      2. Stop hit (worst case if both stop & TP touched same bar)
      3. Final TP hit
      4. First/intermediate TP hit (partial)
      5. Invalidation reason from a higher-level agent
      6. Trailing stop ratchet (no exit, just stop adjustment)
      7. Time-based invalidation
      8. Hold
    """
    cfg = cfg or ExitConfig()

    if safety_emergency:
        return ExitDecision(
            decision=DECISION_EMERGENCY_EXIT,
            reason="safety agent demanded close",
            fill_price=candle.close,
            qty_to_close=pos.quantity,
            new_stop_loss=None,
            is_terminal=True,
        )

    high, low = candle.high, candle.low
    side = pos.side

    # 1) Stop hit?  Conservative tie-break: if both stop and TP could have
    #    been touched in the same bar, assume stop first.
    if pos.stop_loss is not None:
        stop = pos.stop_loss
        if (side == "LONG" and low <= stop) or (side == "SHORT" and high >= stop):
            return ExitDecision(
                decision=DECISION_STOP_HIT,
                reason=f"price hit stop {stop}",
                fill_price=stop,            # assume stop fills at exactly the stop
                qty_to_close=pos.quantity,
                new_stop_loss=None,
                is_terminal=True,
            )

    # 2) Final TP?
    targets = pos.take_profit_targets or []
    if targets:
        final_tp = targets[-1]
        if (side == "LONG" and high >= final_tp) or (side == "SHORT" and low <= final_tp):
            return ExitDecision(
                decision=DECISION_FULL_TP,
                reason=f"final TP {final_tp} hit",
                fill_price=final_tp,
                qty_to_close=pos.quantity,
                new_stop_loss=None,
                is_terminal=True,
            )

        # 3) Intermediate TP? Use the first target the bar reached that we
        #    haven't already exited past. We approximate "exited past" via the
        #    notes — the watcher tags positions when partials happen.
        already = {n for n in pos.notes if n.startswith("partial_tp_at:")}
        for tp in targets[:-1]:
            tag = f"partial_tp_at:{tp}"
            if tag in already:
                continue
            if (side == "LONG" and high >= tp) or (side == "SHORT" and low <= tp):
                qty_close = (pos.quantity * cfg.partial_tp_fraction).quantize(Decimal("1"))
                if qty_close <= 0:
                    qty_close = Decimal("1")
                qty_close = min(qty_close, pos.quantity)
                new_stop = pos.entry_price if cfg.move_to_breakeven_on_first_tp else pos.stop_loss
                return ExitDecision(
                    decision=DECISION_PARTIAL_TP,
                    reason=f"TP {tp} hit; closing {qty_close}/{pos.quantity}, "
                           f"raising stop to breakeven",
                    fill_price=tp,
                    qty_to_close=qty_close,
                    new_stop_loss=new_stop,
                    is_terminal=False,
                )

    # 4) Invalidation reason from a higher-level agent (passed in by watcher).
    if invalidation_reason:
        return ExitDecision(
            decision=DECISION_INVALIDATION_EXIT,
            reason=invalidation_reason,
            fill_price=candle.close,
            qty_to_close=pos.quantity,
            new_stop_loss=None,
            is_terminal=True,
        )

    # 5) Trailing stop — only if ATR available.
    if atr_value is not None and atr_value > 0 and pos.stop_loss is not None:
        if side == "LONG":
            favorable_excursion = candle.high - pos.entry_price
            trigger = cfg.trail_atr_multiple_trigger * atr_value
            if favorable_excursion >= trigger:
                proposed_stop = candle.high - cfg.trail_atr_multiple_keep * atr_value
                if proposed_stop > pos.stop_loss:
                    return ExitDecision(
                        decision=DECISION_TRAIL_STOP,
                        reason=f"price ran {favorable_excursion:.6f} > "
                               f"{trigger:.6f}; tightening stop to {proposed_stop:.6f}",
                        fill_price=None,
                        qty_to_close=Decimal("0"),
                        new_stop_loss=proposed_stop,
                        is_terminal=False,
                    )
        else:  # SHORT
            favorable_excursion = pos.entry_price - candle.low
            trigger = cfg.trail_atr_multiple_trigger * atr_value
            if favorable_excursion >= trigger:
                proposed_stop = candle.low + cfg.trail_atr_multiple_keep * atr_value
                if proposed_stop < pos.stop_loss:
                    return ExitDecision(
                        decision=DECISION_TRAIL_STOP,
                        reason=f"price ran {favorable_excursion:.6f} > "
                               f"{trigger:.6f}; tightening stop to {proposed_stop:.6f}",
                        fill_price=None,
                        qty_to_close=Decimal("0"),
                        new_stop_loss=proposed_stop,
                        is_terminal=False,
                    )

    # 6) Time-based invalidation.
    age_min = _age_minutes(pos.opened_at, candle.close_time_ms)
    if age_min >= cfg.max_hold_minutes:
        # Has it moved in our favor enough to be worth keeping?
        mfe_pct = Decimal("0")
        if pos.margin_usdt > 0:
            mfe_pct = pos.max_favorable_pnl / pos.margin_usdt * Decimal("100")
        if mfe_pct < cfg.min_mfe_pct_of_margin_to_keep_holding:
            return ExitDecision(
                decision=DECISION_INVALIDATION_EXIT,
                reason=f"held {age_min:.0f}m without {cfg.min_mfe_pct_of_margin_to_keep_holding}% MFE; closing",
                fill_price=candle.close,
                qty_to_close=pos.quantity,
                new_stop_loss=None,
                is_terminal=True,
            )

    return ExitDecision(
        decision=DECISION_HOLD,
        reason="all checks pass",
        fill_price=None,
        qty_to_close=Decimal("0"),
        new_stop_loss=None,
        is_terminal=False,
    )


# ----------------------------------------------------------------------------
# Apply: convert a decision into Position state mutations (paper mode).
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class AppliedExit:
    """Result of applying an `ExitDecision` to a `Position`."""

    decision: str
    realized_pnl_delta: Decimal     # this exit's gross PnL contribution
    fees_delta: Decimal             # this exit's fee
    qty_closed: Decimal
    new_status: str                 # position status after applying

    def to_jsonable(self) -> dict:
        return {
            "decision": self.decision,
            "realized_pnl_delta": str(self.realized_pnl_delta),
            "fees_delta": str(self.fees_delta),
            "qty_closed": str(self.qty_closed),
            "new_status": self.new_status,
        }


def apply_decision(
    pos: Position,
    dec: ExitDecision,
    *,
    fee_rate: Decimal = DEFAULT_TAKER_FEE,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    now_iso: str | None = None,
) -> AppliedExit:
    """Mutate ``pos`` per ``dec``. Returns an `AppliedExit` summary.

    For partial fills, qty/realized_pnl/fees are updated incrementally; status
    becomes ``partial_exit`` until everything closes. Terminal decisions set
    ``status=closed`` and stamp ``exit_price``/``exit_reason``.
    """
    now_iso = now_iso or _now_iso()

    # No-op decisions
    if dec.decision == DECISION_HOLD:
        pos.updated_at = now_iso
        return AppliedExit(decision=dec.decision, realized_pnl_delta=Decimal("0"),
                           fees_delta=Decimal("0"), qty_closed=Decimal("0"),
                           new_status=pos.status)

    if dec.decision in (DECISION_TRAIL_STOP, DECISION_MOVE_STOP_BREAKEVEN):
        if dec.new_stop_loss is not None:
            pos.stop_loss = dec.new_stop_loss
            pos.notes.append(f"stop_moved_to:{dec.new_stop_loss} ({dec.reason})")
        pos.updated_at = now_iso
        return AppliedExit(decision=dec.decision, realized_pnl_delta=Decimal("0"),
                           fees_delta=Decimal("0"), qty_closed=Decimal("0"),
                           new_status=pos.status)

    # All other decisions involve closing some qty.
    qty = dec.qty_to_close
    if qty <= 0:
        pos.updated_at = now_iso
        return AppliedExit(decision=dec.decision, realized_pnl_delta=Decimal("0"),
                           fees_delta=Decimal("0"), qty_closed=Decimal("0"),
                           new_status=pos.status)

    fill = dec.fill_price if dec.fill_price is not None else pos.entry_price

    # Apply slippage on partials/exits — paper-mode fills aren't perfect.
    if dec.decision != DECISION_STOP_HIT:
        slip = fill * (slippage_bps / Decimal("10000"))
        if pos.side == "LONG":
            fill = fill - slip                  # exit slightly worse
        else:
            fill = fill + slip
    # Stop hits already incur slippage in the real world; we model it via fee inflation.

    if pos.side == "LONG":
        pnl_per_unit = fill - pos.entry_price
    else:
        pnl_per_unit = pos.entry_price - fill
    gross = pnl_per_unit * qty

    notional_exit = fill * qty
    fees = notional_exit * fee_rate

    # Mutate position
    pos.quantity -= qty
    pos.realized_pnl += gross - fees
    pos.fees_paid_usdt += fees
    pos.updated_at = now_iso

    # Tag partial TPs so we don't re-trigger them next bar.
    if dec.decision == DECISION_PARTIAL_TP and dec.fill_price is not None:
        pos.notes.append(f"partial_tp_at:{dec.fill_price}")
        if dec.new_stop_loss is not None:
            pos.stop_loss = dec.new_stop_loss
            pos.notes.append(f"stop_moved_to:{dec.new_stop_loss}")

    if pos.quantity <= 0 or dec.is_terminal:
        pos.status = "closed"
        pos.closed_at = now_iso
        pos.exit_price = fill
        pos.exit_reason = dec.decision
        # Force qty to zero for cleanliness.
        if dec.is_terminal and pos.quantity > 0:
            # Terminal decision must close the whole position.
            extra_qty = pos.quantity
            extra_pnl = pnl_per_unit * extra_qty
            extra_fees = (fill * extra_qty) * fee_rate
            pos.quantity = Decimal("0")
            pos.realized_pnl += extra_pnl - extra_fees
            pos.fees_paid_usdt += extra_fees
            gross += extra_pnl
            fees += extra_fees
            qty += extra_qty
    else:
        pos.status = "partial_exit"

    return AppliedExit(
        decision=dec.decision,
        realized_pnl_delta=gross,
        fees_delta=fees,
        qty_closed=qty,
        new_status=pos.status,
    )


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _age_minutes(opened_iso: str, now_ms: int) -> float:
    if not opened_iso:
        return 0.0
    try:
        opened = dt.datetime.fromisoformat(opened_iso.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    now = dt.datetime.fromtimestamp(now_ms / 1000.0, tz=opened.tzinfo or dt.timezone.utc)
    return (now - opened).total_seconds() / 60.0


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


__all__ = [
    "DECISION_HOLD",
    "DECISION_PARTIAL_TP",
    "DECISION_FULL_TP",
    "DECISION_STOP_HIT",
    "DECISION_TRAIL_STOP",
    "DECISION_MOVE_STOP_BREAKEVEN",
    "DECISION_INVALIDATION_EXIT",
    "DECISION_EMERGENCY_EXIT",
    "ExitConfig",
    "ExitDecision",
    "AppliedExit",
    "decide_from_candle",
    "apply_decision",
]
