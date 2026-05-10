"""Safety/Kill-Switch Agent's health probe.

Read-only. Returns a structured snapshot of:
  - Binance public API reachability and latency
  - Server-time vs local-time skew (Binance rejects signed requests with skew
    > 1 s by default; relevant for Phase 4)
  - Recent system-health.json signals (daily PnL, consecutive losses)
  - Whether trading should be allowed *right now*

The orchestrator calls this *before* every cycle. If `trading_allowed=False`,
it must abort the cycle.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .binance_client import BinanceAPIError, BinanceClient


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_HEALTH = _PROJECT_ROOT / "data" / "system-health.json"
RISK_STATE = _PROJECT_ROOT / "data" / "risk-state.json"


@dataclass(frozen=True)
class HealthReport:
    api_reachable: bool
    api_latency_ms: int | None
    server_time_skew_ms: int | None      # +ve = our clock is behind
    daily_pnl_usdt: float
    consecutive_losses: int
    trading_paused: bool
    paused_reason: str | None
    trading_allowed: bool
    warnings: tuple[str, ...]
    timestamp: str

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "api_reachable": self.api_reachable,
            "api_latency_ms": self.api_latency_ms,
            "server_time_skew_ms": self.server_time_skew_ms,
            "daily_pnl_usdt": self.daily_pnl_usdt,
            "consecutive_losses": self.consecutive_losses,
            "trading_paused": self.trading_paused,
            "paused_reason": self.paused_reason,
            "trading_allowed": self.trading_allowed,
            "warnings": list(self.warnings),
            "timestamp": self.timestamp,
        }


def run_health_check(client: BinanceClient | None = None) -> HealthReport:
    client = client or BinanceClient()
    warnings: list[str] = []

    api_ok = False
    latency_ms: int | None = None
    skew_ms: int | None = None
    try:
        t0 = time.monotonic()
        result = client.get("/fapi/v1/time")
        latency_ms = int((time.monotonic() - t0) * 1000)
        api_ok = True
        server_ms = int(result["serverTime"])
        local_ms = int(time.time() * 1000)
        skew_ms = local_ms - server_ms
        if abs(skew_ms) > 5_000:
            warnings.append(f"clock skew {skew_ms} ms vs Binance — sign requests will fail in live mode")
    except BinanceAPIError as e:
        warnings.append(f"Binance API not reachable: {e}")
    except Exception as e:
        warnings.append(f"unexpected health-check error: {e!r}")

    risk = _load_json(RISK_STATE) or {}
    sys = _load_json(SYSTEM_HEALTH) or {}

    daily_pnl = float(risk.get("daily_pnl_usdt") or 0)
    consecutive = int(risk.get("consecutive_losses") or 0)
    consecutive_limit = int(risk.get("consecutive_loss_limit") or 3)
    paused = bool(sys.get("trading_paused") or risk.get("trading_paused") or False)
    paused_reason = sys.get("paused_reason")

    if consecutive >= consecutive_limit:
        warnings.append(
            f"consecutive losses {consecutive} >= limit {consecutive_limit} — Safety Agent should pause"
        )
        paused = True
        paused_reason = paused_reason or "consecutive-loss limit reached"

    trading_allowed = api_ok and not paused

    return HealthReport(
        api_reachable=api_ok,
        api_latency_ms=latency_ms,
        server_time_skew_ms=skew_ms,
        daily_pnl_usdt=daily_pnl,
        consecutive_losses=consecutive,
        trading_paused=paused,
        paused_reason=paused_reason,
        trading_allowed=trading_allowed,
        warnings=tuple(warnings),
        timestamp=dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


__all__ = ["HealthReport", "run_health_check"]
