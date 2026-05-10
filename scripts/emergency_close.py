"""Emergency close — kill all open Binance Futures positions.

Reads `/fapi/v2/positionRisk` (NOT `data/open-positions.json` — when in doubt,
trust the exchange), then for each non-zero position places a `reduceOnly=True`
MARKET order against it. After all closes, re-fetches positions and verifies
every one is now flat.

Used by:
  - `scripts/run_emergency_close.py` (the /emergency-shutdown slash command's
    target)
  - `scripts/watcher.py` when an exit_simulator emergency_exit decision is
    raised

Always logs to memory/safety-events.md.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .account import Account, ExchangePosition
from .binance_signed_client import SignedRequestsDisabledError
from .journal_writer import append_safety_event
from .live_execution import LiveExecution, OrderResult
from .symbol_filters import SymbolSpec, parse_exchange_info

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloseAttempt:
    symbol: str
    side: str                  # the side of the position being closed
    quantity: Decimal
    order_result: OrderResult | None
    error: str | None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": str(self.quantity),
            "order_result": self.order_result.to_jsonable() if self.order_result else None,
            "error": self.error,
        }


@dataclass(frozen=True)
class EmergencyCloseReport:
    initiated_at: str
    completed_at: str
    initial_open_positions: int
    attempts: tuple[CloseAttempt, ...]
    residual_open_positions: int
    success: bool                       # True iff every position is flat after close

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "initiated_at": self.initiated_at,
            "completed_at": self.completed_at,
            "initial_open_positions": self.initial_open_positions,
            "attempts": [a.to_jsonable() for a in self.attempts],
            "residual_open_positions": self.residual_open_positions,
            "success": self.success,
        }


def emergency_close_all(
    *,
    account: Account | None = None,
    execution: LiveExecution | None = None,
    spec_map: dict[str, SymbolSpec] | None = None,
    reason: str = "manual emergency",
) -> EmergencyCloseReport:
    """Close every open Binance Futures position with reduce-only market orders.

    Args:
        account: signed Account client (defaults to a fresh one).
        execution: signed LiveExecution client.
        spec_map: pre-fetched ``{symbol: SymbolSpec}`` (saves a weight-1 call).
        reason: free-text recorded in the Safety Event log.

    Returns an `EmergencyCloseReport`. ``success=True`` only if every position
    is verifiably flat after the close pass.
    """
    initiated = _now_iso()
    account = account or Account()
    execution = execution or LiveExecution()

    try:
        positions = account.get_open_positions()
    except SignedRequestsDisabledError as e:
        _log_event(initiated, reason, "blocked: " + str(e), positions_affected=[])
        raise

    initial = len(positions)
    if initial == 0:
        completed = _now_iso()
        return _empty_report(initiated, completed, reason)

    if spec_map is None:
        from .market_data import MarketData
        from .binance_client import BinanceClient
        market = MarketData(BinanceClient(base_url=execution.client.base_url))
        spec_map = parse_exchange_info(market.get_exchange_info())

    attempts: list[CloseAttempt] = []
    for pos in positions:
        spec = spec_map.get(pos.symbol)
        if spec is None:
            attempts.append(CloseAttempt(
                symbol=pos.symbol, side=pos.side, quantity=pos.quantity,
                order_result=None, error="symbol not in exchangeInfo — cannot validate",
            ))
            continue

        try:
            result = execution.close_position_market(
                spec,
                position_side=pos.side,
                quantity=pos.quantity,
                client_order_id=f"EMG-{spec.symbol[:10]}-{int(dt.datetime.utcnow().timestamp())}",
            )
            attempts.append(CloseAttempt(
                symbol=pos.symbol, side=pos.side, quantity=pos.quantity,
                order_result=result, error=None,
            ))
        except Exception as e:
            attempts.append(CloseAttempt(
                symbol=pos.symbol, side=pos.side, quantity=pos.quantity,
                order_result=None, error=f"{type(e).__name__}: {e}",
            ))

    # Verify residual.
    try:
        residual_positions = account.get_open_positions()
    except Exception as e:
        log.error("post-close residual check failed: %r", e)
        residual_positions = []

    residual = len(residual_positions)
    success = residual == 0 and all(
        a.error is None and a.order_result and a.order_result.success
        for a in attempts
    )
    completed = _now_iso()

    report = EmergencyCloseReport(
        initiated_at=initiated,
        completed_at=completed,
        initial_open_positions=initial,
        attempts=tuple(attempts),
        residual_open_positions=residual,
        success=success,
    )
    _log_event(
        initiated, reason,
        f"closed {sum(1 for a in attempts if a.order_result and a.order_result.success)}/{initial}; "
        f"residual {residual}",
        positions_affected=[a.symbol for a in attempts],
    )
    return report


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _empty_report(initiated: str, completed: str, reason: str) -> EmergencyCloseReport:
    _log_event(initiated, reason, "no open positions — emergency close was a no-op", positions_affected=[])
    return EmergencyCloseReport(
        initiated_at=initiated, completed_at=completed,
        initial_open_positions=0, attempts=tuple(),
        residual_open_positions=0, success=True,
    )


def _log_event(initiated: str, reason: str, action_taken: str,
               positions_affected: list[str]) -> None:
    append_safety_event({
        "timestamp": initiated,
        "mode": "LIVE" if positions_affected else "LIVE",
        "event_type": "emergency_exit",
        "triggered_by": "safety-agent",
        "details": reason,
        "positions_affected": positions_affected,
        "action_taken": action_taken,
        "duration_minutes": 0,
        "resolved_at": _now_iso(),
        "resolution_notes": "emergency_close_all completed",
    })


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


__all__ = ["CloseAttempt", "EmergencyCloseReport", "emergency_close_all"]
