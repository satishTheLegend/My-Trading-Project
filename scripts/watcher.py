"""Watcher Agent — single monitoring tick over all open positions.

For each open `Position`:
  1. Fetch the latest 1m candle + recent ATR window for the symbol.
  2. Update mark-to-market PnL, MFE, MAE.
  3. Run `exit_simulator.decide_from_candle`.
  4. Apply the decision via `exit_simulator.apply_decision`.
     - In paper mode, decisions mutate local state directly.
     - In live modes, `apply_decision` refuses to close a position on a
       local-price comparison. Closures are written only after Binance
       confirms zero qty (via `binance_position_sync`) or after a reduce-
       only fill arrives on a known algoId. Trailing-stop moves are also
       refused unless the watcher is wired with a `live_executor` that can
       cancel-and-replace the SL algo order on the exchange.
  5. Persist position changes.
  6. If terminal, append a closed-trade entry to memory/trade-journal.md.
  7. Surface live/exchange divergence as a SAFETY warning.

Designed for a single tick — looping cadence is the orchestrator's concern.

Historical note
---------------
On 2026-05-11 the previous watcher trailed a LOCAL stop_loss upward without
updating the exchange STOP_MARKET algoOrder. When price later dipped below
the locally-trailed (but exchange-unknown) SL, the watcher marked the
position closed in `data/open-positions.json` while the live position was
still wide open at Binance — uPnL +0.38 USDT, original SL/TP algos still
NEW. This file's safety design is a direct response to that incident.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .exit_simulator import (
    AppliedExit,
    DECISION_TRAIL_STOP,
    ExitConfig,
    ExitDecision,
    LIVE_MODES,
    apply_decision,
    decide_from_candle,
)
from .indicators import atr
from .journal_writer import append_paper_trade, append_safety_event
from .market_data import Candle, MarketData
from .positions_store import Position, PositionsStore
from .safety_state import SafetyStateManager
from .symbol_filters import SymbolSpec

log = logging.getLogger(__name__)


# Trailing stops are opt-in. Disabled by default in every mode until the
# cancel-and-replace path has been exercised end-to-end against a live
# bracket. Toggled via the EXIT_TRAILING_STOP_ENABLED env var.
def _trailing_enabled_default() -> bool:
    raw = os.environ.get("EXIT_TRAILING_STOP_ENABLED", "").strip().lower()
    return raw in {"true", "1", "yes", "on"}


@dataclass
class WatcherTickReport:
    positions_checked: int = 0
    decisions: list[dict[str, Any]] = field(default_factory=list)
    closed: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "positions_checked": self.positions_checked,
            "decisions": self.decisions,
            "closed": self.closed,
            "warnings": self.warnings,
        }


def watch_open_positions(
    market: MarketData,
    *,
    store: PositionsStore | None = None,
    cfg: ExitConfig | None = None,
    candle_interval: str = "1m",
    candle_lookback: int = 30,
    safety_emergency: bool = False,
    safety_manager: SafetyStateManager | None = None,
    live_executor: Any = None,
    symbol_specs: dict[str, SymbolSpec] | None = None,
    enable_trailing: bool | None = None,
    exchange_positions: list[Any] | None = None,
) -> WatcherTickReport:
    """Run one watcher tick. Returns a structured report.

    Parameters
    ----------
    market : MarketData
        Public candle source. Required.
    store : PositionsStore, optional
        Defaults to the project-wide store.
    cfg : ExitConfig, optional
        Tunables for the exit logic.
    candle_interval, candle_lookback :
        Klines fetched per symbol.
    safety_emergency : bool
        If True, every position emits an EMERGENCY_EXIT decision this tick.
    safety_manager : SafetyStateManager, optional
        For recording realized PnL on a paper-mode close.
    live_executor :
        Optional ``LiveExecution`` instance. When provided AND
        ``enable_trailing`` is True AND the position is in a live mode,
        the watcher will atomically cancel the existing SL algoOrder and
        place a new one at the trailed price before mutating local state.
    symbol_specs :
        ``{symbol: SymbolSpec}`` map — required when ``live_executor`` is
        passed and trailing is enabled, because the algoOrder placement
        helper needs the symbol's tick/qty/min-notional filters.
    enable_trailing : bool, optional
        Override for the ``EXIT_TRAILING_STOP_ENABLED`` env var. Defaults
        to the env var value (which itself defaults to False).
    exchange_positions :
        Optional pre-fetched ``list[ExchangePosition]`` — when supplied,
        the watcher checks every local-open position against the exchange
        snapshot and emits a SAFETY warning on any divergence.

    The watcher is intentionally idempotent: calling it twice in a row with
    no new candle produces only a HOLD decision with no journal writes.
    Mark-to-market updates *do* persist on every call.
    """
    store = store or PositionsStore()
    cfg = cfg or ExitConfig()
    safety_manager = safety_manager or SafetyStateManager()
    if enable_trailing is None:
        enable_trailing = _trailing_enabled_default()

    report = WatcherTickReport()
    open_positions = store.load_open()
    report.positions_checked = len(open_positions)
    if not open_positions:
        return report

    # Optional pre-tick guardrail: if the caller supplied a fresh exchange
    # snapshot, verify every local-open position has a non-zero exchange
    # counterpart on the same side. A mismatch is a SAFETY-grade event.
    if exchange_positions is not None:
        _emit_exchange_divergence_warnings(open_positions, exchange_positions, report)

    # Persistence model — see memory/execution-errors.md ERROR-20260511-6.
    # The watcher MUST NOT use ``store.save_all`` because it rewrites the
    # whole file from a stale in-memory snapshot and clobbers any concurrent
    # writer (execution router, PnL auto-adjust monitor, reconciliation,
    # emergency-close) that landed between this tick's load and write.
    #
    # Routing:
    #   * Normal tick (mark-to-market + MFE/MAE) → ``watcher_updates`` map,
    #     flushed at end via ``store.apply_watcher_updates`` (whitelist
    #     read-modify-write under file lock).
    #   * Paper-mode close → ``store.upsert`` for that one Position
    #     (legitimate full write, the watcher owns paper-mode closes).
    #   * Live-mode trail SUCCESS → ``store.upsert`` for that one Position
    #     (legitimate full write — the exchange algoOrder has already been
    #     cancel-and-replaced, so persisting stop_loss + algo_order_ids
    #     atomically is now correct).
    watcher_updates: dict[str, dict[str, Any]] = {}
    full_upserts: list[Position] = []

    # Snapshot the watcher's starting view of each position so we can diff
    # at end-of-tick and only emit whitelisted-field updates that actually
    # changed.
    initial_snapshot: dict[str, dict[str, Any]] = {
        p.position_id: {
            "unrealized_pnl": p.unrealized_pnl,
            "max_favorable_pnl": p.max_favorable_pnl,
            "max_adverse_pnl": p.max_adverse_pnl,
            "notes_len": len(p.notes),
        }
        for p in open_positions
    }

    for pos in open_positions:
        try:
            candles = market.get_klines(pos.symbol, candle_interval, limit=candle_lookback)
        except Exception as e:
            report.warnings.append(f"{pos.symbol}: failed to fetch candles ({e!r})")
            continue
        if not candles:
            report.warnings.append(f"{pos.symbol}: empty candle response")
            continue

        latest = candles[-1]
        # Update mark-to-market on close price (conservative; mark price would
        # be slightly different but we don't always have it for free here).
        pos.update_pnl(latest.close)

        # Compute ATR over the lookback window for trailing logic.
        atr_value: Decimal | None = None
        if len(candles) >= 15:
            atr_series = atr(candles, period=14)
            last_atr = atr_series[-1]
            if last_atr == last_atr:           # not NaN
                atr_value = Decimal(str(last_atr))

        # Suppress trailing entirely when disabled — the decision function
        # gates on ``atr_value`` to emit TRAIL_STOP, so passing None here
        # short-circuits the trail branch without touching its internals.
        atr_for_decision = atr_value if enable_trailing else None

        decision = decide_from_candle(
            pos, latest,
            cfg=cfg,
            atr_value=atr_for_decision,
            safety_emergency=safety_emergency,
        )

        # Live-mode trailing: attempt cancel-and-replace via the executor.
        # If anything fails, we leave both local and exchange state untouched
        # and emit a warning. NEVER mutate the LOCAL stop_loss in live mode
        # without exchange confirmation.
        if (
            decision.decision == DECISION_TRAIL_STOP
            and pos.mode in LIVE_MODES
            and enable_trailing
        ):
            handled = _try_live_trailing(
                pos=pos,
                decision=decision,
                executor=live_executor,
                symbol_specs=symbol_specs,
                report=report,
            )
            # Whether the live trail succeeded or not, apply_decision is
            # still called so the journal records the attempt — but in live
            # mode apply_decision refuses to mutate state by itself, which
            # is exactly what we want (the executor branch handled the
            # mutation when it succeeded).
            if handled:
                # Trail succeeded — manually update the local fields here
                # so apply_decision doesn't no-op the move below.
                pos.stop_loss = decision.new_stop_loss
                pos.notes.append(
                    f"stop_moved_to:{decision.new_stop_loss} ({decision.reason}) "
                    f"[exchange algo replaced atomically]"
                )
                pos.updated_at = _now_iso()
                applied = AppliedExit(
                    decision=decision.decision,
                    realized_pnl_delta=Decimal("0"),
                    fees_delta=Decimal("0"),
                    qty_closed=Decimal("0"),
                    new_status=pos.status,
                )
            else:
                # Trail failed or no executor — apply_decision will no-op.
                applied = apply_decision(pos, decision)
        else:
            applied = apply_decision(pos, decision)

        report.decisions.append({
            "position_id": pos.position_id,
            "symbol": pos.symbol,
            "decision": decision.to_jsonable(),
            "applied": applied.to_jsonable(),
            "unrealized_pnl_after": str(pos.unrealized_pnl),
            "realized_pnl_after": str(pos.realized_pnl),
        })

        # Decide how to persist this position's mutations.
        #
        # Cases that require a full single-position upsert (the watcher
        # legitimately owns these writes):
        #   1. Paper-mode close — pos.status flipped to "closed".
        #   2. Live-mode trail SUCCESS — the exchange algoOrder has been
        #      cancel-and-replaced; stop_loss + algo_order_ids must persist
        #      atomically with the new note. ``apply_decision`` returned an
        #      AppliedExit with decision=DECISION_TRAIL_STOP and the live
        #      branch executed (handled=True path above).
        #
        # All other ticks must go through the whitelist path to avoid
        # clobbering concurrent writers.
        is_live_trail_success = (
            pos.mode in LIVE_MODES
            and applied.decision == DECISION_TRAIL_STOP
        )
        if pos.status == "closed" or is_live_trail_success:
            full_upserts.append(pos)
        else:
            snap = initial_snapshot.get(pos.position_id, {})
            updates: dict[str, Any] = {}
            if pos.unrealized_pnl != snap.get("unrealized_pnl"):
                updates["unrealized_pnl"] = pos.unrealized_pnl
            if pos.max_favorable_pnl != snap.get("max_favorable_pnl"):
                updates["max_favorable_pnl"] = pos.max_favorable_pnl
            if pos.max_adverse_pnl != snap.get("max_adverse_pnl"):
                updates["max_adverse_pnl"] = pos.max_adverse_pnl
            notes_len_before = snap.get("notes_len", len(pos.notes))
            if len(pos.notes) > notes_len_before:
                updates["notes"] = pos.notes[notes_len_before:]
            if updates:
                watcher_updates[pos.position_id] = updates

        if pos.status == "closed":
            # Only reachable in paper mode now (live-mode apply_decision
            # refuses to flip status on local-price terminals). Keep the
            # journaling path intact for paper trades.
            report.closed.append({
                "position_id": pos.position_id,
                "symbol": pos.symbol,
                "exit_reason": pos.exit_reason,
                "exit_price": str(pos.exit_price) if pos.exit_price else None,
                "realized_pnl": str(pos.realized_pnl),
            })
            _journal_closed_trade(pos)

            # Update central safety state. ``realized_pnl`` is the position's
            # final net PnL (gross − fees, accumulated across partials). The
            # SafetyStateManager handles auto-pause if a limit is breached.
            try:
                state = safety_manager.record_trade_close(
                    net_pnl_usdt=pos.realized_pnl, symbol=pos.symbol,
                )
                if state.trading_paused and state.paused_reason:
                    report.warnings.append(
                        f"safety pause triggered: {state.paused_reason}"
                    )
            except Exception as e:
                report.warnings.append(f"safety state update failed: {e!r}")

        if applied.decision == "emergency_exit" and pos.mode not in LIVE_MODES:
            # Paper-mode emergency: record a safety event as before. Live-mode
            # emergencies are driven by `scripts.emergency_close` / `run_emergency_close`
            # which writes its own safety event with the real exchange fills.
            append_safety_event({
                "timestamp": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "mode": pos.mode,
                "event_type": "emergency_exit",
                "triggered_by": "watcher-agent",
                "details": decision.reason,
                "positions_affected": [pos.position_id],
                "action_taken": "closed at market",
                "duration_minutes": 0,
                "resolved_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "resolution_notes": "watcher tick",
            })

    # Flush. ``apply_watcher_updates`` is the safe path — it locks the
    # file, re-reads it, merges only the whitelisted fields into the
    # matched rows, and writes the result back atomically. ``upsert`` is
    # used only for the two legitimate full-write cases (paper-mode close,
    # live-mode trail success); both also lock the file.
    if watcher_updates:
        store.apply_watcher_updates(watcher_updates)
    for pos in full_upserts:
        store.upsert(pos)
    return report


# ----------------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------------


def _try_live_trailing(
    *,
    pos: Position,
    decision: ExitDecision,
    executor: Any,
    symbol_specs: dict[str, SymbolSpec] | None,
    report: WatcherTickReport,
) -> bool:
    """Cancel-and-replace the SL algoOrder on the exchange.

    Returns True only if BOTH the cancel and the place succeeded. Any failure
    leaves local state untouched and appends a warning to the report.
    """
    if executor is None:
        report.warnings.append(
            f"{pos.symbol}: trail_stop suppressed — no live_executor wired "
            f"into watcher (would move SL to {decision.new_stop_loss})"
        )
        return False

    spec = (symbol_specs or {}).get(pos.symbol)
    if spec is None:
        report.warnings.append(
            f"{pos.symbol}: trail_stop suppressed — no SymbolSpec provided "
            f"for live trail (would move SL to {decision.new_stop_loss})"
        )
        return False

    sl_algo_id = pos.algo_order_ids.get("sl")
    if not sl_algo_id:
        report.warnings.append(
            f"{pos.symbol}: trail_stop suppressed — no SL algoId on Position "
            f"record (would move SL to {decision.new_stop_loss})"
        )
        return False

    if decision.new_stop_loss is None:
        report.warnings.append(
            f"{pos.symbol}: trail_stop has no new_stop_loss — skipping"
        )
        return False

    # 1) Cancel the existing SL algo. If this fails, abort.
    try:
        executor.cancel_algo_order(pos.symbol, algo_id=sl_algo_id)
    except Exception as e:
        report.warnings.append(
            f"{pos.symbol}: trail_stop cancel-old-SL failed ({e!r}) — "
            f"leaving exchange and local state UNCHANGED"
        )
        return False

    # 2) Place the new SL algo at the trailed price.
    exit_side = "SELL" if pos.side == "LONG" else "BUY"
    try:
        result = executor.place_algo_stop_market(
            spec,
            side=exit_side,
            stop_price=decision.new_stop_loss,
            quantity=pos.quantity,
            working_type="MARK_PRICE",
            price_protect=True,
        )
    except Exception as e:
        # CRITICAL: the old SL is already cancelled. The position is now
        # naked on the exchange. Surface a high-severity warning so the
        # safety agent / operator can intervene immediately.
        report.warnings.append(
            f"SAFETY-CRITICAL {pos.symbol}: trail_stop place-new-SL FAILED "
            f"({e!r}) AFTER old SL was cancelled — position is NAKED on the "
            f"exchange. Manual intervention required to re-place SL at "
            f"{decision.new_stop_loss} or at the prior level."
        )
        pos.notes.append(
            f"naked_after_trail_replace_failure at {_now_iso()}: "
            f"old SL algoId {sl_algo_id} cancelled, new SL at "
            f"{decision.new_stop_loss} FAILED to place ({e!r})"
        )
        return False

    if not result.success:
        report.warnings.append(
            f"SAFETY-CRITICAL {pos.symbol}: trail_stop place-new-SL returned "
            f"failure ({result.error_msg}) AFTER old SL was cancelled — "
            f"position is NAKED on the exchange. Manual intervention required."
        )
        return False

    # 3) Both succeeded — update the local algoId reference. The caller will
    #    update stop_loss and notes after this returns True.
    new_id = result.order_id
    if new_id is not None:
        pos.algo_order_ids["sl"] = str(new_id)
    return True


def _emit_exchange_divergence_warnings(
    local_open: list[Position],
    exch_positions: list[Any],
    report: WatcherTickReport,
) -> None:
    """Compare local-open positions against the exchange snapshot.

    The exchange-position objects must have ``.symbol``, ``.side`` (LONG/
    SHORT/FLAT), and ``.quantity`` attributes (matches ``ExchangePosition``).
    """
    by_symbol: dict[str, Any] = {}
    for ep in exch_positions:
        sym = getattr(ep, "symbol", None)
        if not sym:
            continue
        is_open = getattr(ep, "is_open", None)
        if is_open is None:
            qty = getattr(ep, "quantity", Decimal("0"))
            is_open = qty != 0
        if is_open:
            by_symbol[sym] = ep

    for lp in local_open:
        ep = by_symbol.get(lp.symbol)
        if ep is None:
            report.warnings.append(
                f"SAFETY {lp.symbol}: local says open ({lp.side} {lp.quantity}) "
                f"but exchange shows no position — escalate to "
                f"safety-kill-switch-agent. Do NOT mutate local state from "
                f"this tick."
            )
            continue
        ep_side = getattr(ep, "side", "")
        if ep_side and lp.side != ep_side:
            report.warnings.append(
                f"SAFETY {lp.symbol}: local side {lp.side} vs exchange side "
                f"{ep_side} — escalate to safety-kill-switch-agent."
            )


def _journal_closed_trade(pos: Position) -> None:
    """Append a fully-realized trade to memory/trade-journal.md."""
    net_pnl = pos.realized_pnl
    entry = {
        "trade_id": f"TRADE-{dt.datetime.utcnow():%Y%m%d-%H%M%S}",
        "proposal_id": pos.proposal_id,
        "mode": pos.mode,
        "symbol": pos.symbol,
        "side": pos.side,
        "strategy": pos.strategy,
        "market_regime": pos.market_regime,
        "entry_time": pos.opened_at,
        "entry_price": str(pos.entry_price),
        "quantity": str(pos.initial_quantity),
        "leverage": pos.leverage,
        "margin_mode": pos.margin_mode,
        "margin_usdt": str(pos.margin_usdt),
        "notional_usdt": str(pos.notional_usdt),
        "stop_loss": str(pos.stop_loss) if pos.stop_loss is not None else "null",
        "take_profit_targets": [str(t) for t in pos.take_profit_targets],
        "exit_time": pos.closed_at,
        "exit_price": str(pos.exit_price) if pos.exit_price is not None else "null",
        "exit_reason": pos.exit_reason or "unknown",
        "gross_pnl_usdt": str(pos.realized_pnl + pos.fees_paid_usdt),
        "fees_usdt": str(pos.fees_paid_usdt),
        "funding_usdt": str(pos.funding_paid_usdt),
        "slippage_usdt": "0",   # already baked into average_price/realized_pnl
        "net_pnl_usdt": str(net_pnl),
        "max_favorable_pnl_usdt": str(pos.max_favorable_pnl),
        "max_adverse_pnl_usdt": str(pos.max_adverse_pnl),
        "mistake_tags": pos.mistake_tags,
        "lessons": "; ".join(pos.notes[-5:]) if pos.notes else "",
        "order_ids": pos.order_ids,
    }
    append_paper_trade(entry)


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


__all__ = [
    "WatcherTickReport",
    "watch_open_positions",
]
