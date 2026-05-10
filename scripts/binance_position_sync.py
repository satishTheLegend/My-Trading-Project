"""Binance position sync — the Binance Sync Agent's executable surface.

Wraps `scripts/account.py`, `scripts/positions_store.py`, and
`scripts/position_manager.py` into a single CLI/entrypoint that:

  1. Fetches Binance wallet + open positions + open orders.
  2. Compares against `data/open-positions.json`.
  3. Detects manual positions (Binance has it, local doesn't, or no
     `proposal_id`).
  4. Writes `data/synced-binance-positions.json` and
     `data/manual-positions.json`.
  5. Optionally calls the Telegram Notifier.

CLI::

    python -m scripts.binance_position_sync
    python -m scripts.binance_position_sync --notify-telegram
    python -m scripts.binance_position_sync --pause-on-mismatch
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from .account import Account, ExchangePosition
from .binance_signed_client import SignedClient
from .position_manager import (
    Mismatch, ReconciliationReport, reconcile, record_health,
)
from .positions_store import PositionsStore

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYNCED_BINANCE = _PROJECT_ROOT / "data" / "synced-binance-positions.json"
MANUAL_POSITIONS = _PROJECT_ROOT / "data" / "manual-positions.json"


# ----------------------------------------------------------------------------
# Result types
# ----------------------------------------------------------------------------


@dataclass
class ManualPositionRecord:
    symbol: str
    side: str
    quantity: str
    entry_price: str
    mark_price: str
    leverage: int
    margin_type: str
    unrealized_pnl: str
    liquidation_price: str | None
    first_seen_at: str
    agency_managed: bool

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "mark_price": self.mark_price,
            "leverage": self.leverage,
            "margin_type": self.margin_type,
            "unrealized_pnl": self.unrealized_pnl,
            "liquidation_price": self.liquidation_price,
            "first_seen_at": self.first_seen_at,
            "agency_managed": self.agency_managed,
        }


@dataclass
class SyncReport:
    sync_status: str               # "success" | "warning" | "failed"
    wallet_balance_usdt: str
    available_margin_usdt: str
    open_positions_count: int
    manual_positions_detected: list[dict[str, Any]] = field(default_factory=list)
    state_mismatches: list[dict[str, Any]] = field(default_factory=list)
    new_trades_allowed: bool = True
    notes: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "sync_status": self.sync_status,
            "wallet_balance_usdt": self.wallet_balance_usdt,
            "available_margin_usdt": self.available_margin_usdt,
            "open_positions_count": self.open_positions_count,
            "manual_positions_detected": self.manual_positions_detected,
            "state_mismatches": self.state_mismatches,
            "new_trades_allowed": self.new_trades_allowed,
            "notes": self.notes,
            "timestamp": self.timestamp,
        }


# ----------------------------------------------------------------------------
# Sync routine
# ----------------------------------------------------------------------------


def sync_binance(
    *,
    account: Account | None = None,
    store: PositionsStore | None = None,
    notify_telegram: bool = False,
    pause_on_mismatch: bool = False,
) -> SyncReport:
    account = account or Account()
    store = store or PositionsStore()

    notes: list[str] = []
    sync_status = "success"
    wallet = "0"
    avail = "0"
    exch_positions: list[ExchangePosition] = []

    try:
        balances = account.get_balances()
        usdt = next((b for b in balances if b.asset == "USDT"), None)
        if usdt is not None:
            wallet = str(usdt.wallet_balance)
            avail = str(usdt.available_balance)
        exch_positions = account.get_open_positions()
    except Exception as e:
        sync_status = "failed"
        notes.append(f"Binance read error: {type(e).__name__}: {e}")

    local_positions = store.load_open()
    recon = reconcile(local_positions=local_positions, exchange_positions=exch_positions)

    # Manual positions = exchange-side positions that the reconciler flagged
    # ``missing_locally``. Persist them with a first-seen timestamp.
    existing_manual = _load_existing_manual()
    now = _now_iso()
    manual_records: list[dict[str, Any]] = []
    new_manuals: list[dict[str, Any]] = []
    for m in recon.mismatches:
        if m.kind != "missing_locally" or m.exchange is None:
            continue
        first_seen = existing_manual.get(m.symbol, {}).get("first_seen_at", now)
        record = ManualPositionRecord(
            symbol=m.symbol,
            side=m.exchange.get("side", ""),
            quantity=m.exchange.get("quantity", "0"),
            entry_price=m.exchange.get("entry_price", "0"),
            mark_price=m.exchange.get("mark_price", "0"),
            leverage=int(m.exchange.get("leverage", 1)),
            margin_type=m.exchange.get("margin_type", ""),
            unrealized_pnl=str(_extract_unreal(exch_positions, m.symbol)),
            liquidation_price=m.exchange.get("liquidation_price"),
            first_seen_at=first_seen,
            agency_managed=False,
        )
        manual_records.append(record.to_jsonable())
        if m.symbol not in existing_manual:
            new_manuals.append(record.to_jsonable())

    _write_manual(manual_records, last_detected_at=now)
    _write_synced(exch_positions, wallet, avail)

    new_trades_allowed = recon.is_clean
    if not new_trades_allowed:
        sync_status = "warning"
        record_health(recon, pause_on_mismatch=pause_on_mismatch)

    if notify_telegram and new_manuals:
        _try_notify_telegram(new_manuals)

    return SyncReport(
        sync_status=sync_status,
        wallet_balance_usdt=wallet,
        available_margin_usdt=avail,
        open_positions_count=len(exch_positions),
        manual_positions_detected=manual_records,
        state_mismatches=[m.to_jsonable() for m in recon.mismatches],
        new_trades_allowed=new_trades_allowed,
        notes=notes,
        timestamp=now,
    )


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _extract_unreal(positions: list[ExchangePosition], symbol: str) -> Decimal:
    for p in positions:
        if p.symbol == symbol:
            return p.un_realized_profit
    return Decimal("0")


def _load_existing_manual() -> dict[str, dict[str, Any]]:
    if not MANUAL_POSITIONS.exists():
        return {}
    try:
        data = json.loads(MANUAL_POSITIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {entry["symbol"]: entry for entry in data.get("manual_positions", [])}


def _write_manual(records: list[dict[str, Any]], *, last_detected_at: str) -> None:
    MANUAL_POSITIONS.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "manual_positions": records,
        "last_detected_at": last_detected_at,
    }
    _atomic_write(MANUAL_POSITIONS, json.dumps(payload, indent=2))


def _write_synced(positions: list[ExchangePosition], wallet: str, avail: str) -> None:
    SYNCED_BINANCE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "positions": [
            {
                "symbol": p.symbol,
                "side": p.side,
                "quantity": str(p.quantity),
                "entry_price": str(p.entry_price),
                "mark_price": str(p.mark_price),
                "unrealized_pnl": str(p.un_realized_profit),
                "leverage": p.leverage,
                "margin_type": p.margin_type,
                "liquidation_price": str(p.liquidation_price) if p.liquidation_price is not None else None,
            }
            for p in positions
        ],
        "wallet_balance_usdt": wallet,
        "available_margin_usdt": avail,
        "synced_at": _now_iso(),
    }
    _atomic_write(SYNCED_BINANCE, json.dumps(payload, indent=2))


def _atomic_write(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=".tmp.", delete=False,
    ) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def _try_notify_telegram(new_manuals: list[dict[str, Any]]) -> None:
    try:
        from .telegram_notifier import send_manual_position_alert
    except Exception:
        log.debug("telegram_notifier not available; skipping manual-position alert")
        return
    for m in new_manuals:
        try:
            send_manual_position_alert(m)
        except Exception as e:
            log.warning("telegram manual-position alert failed: %r", e)


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sync Binance positions/wallet/orders")
    p.add_argument("--notify-telegram", action="store_true",
                   help="send Telegram alerts for newly-detected manual positions")
    p.add_argument("--pause-on-mismatch", action="store_true",
                   help="set trading_paused=true in system-health.json on mismatch")
    p.add_argument("--no-permission-check", action="store_true",
                   help="(testnet only) skip the withdrawal-permission probe")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    client = SignedClient()
    client.enable_signed_requests()
    account = Account(client)
    if not args.no_permission_check:
        perms = account.check_permissions()
        if not perms.is_safe_to_trade:
            print(json.dumps({
                "error": "permission preflight failed",
                "notes": list(perms.notes),
            }, indent=2))
            return 1

    report = sync_binance(
        account=account,
        notify_telegram=args.notify_telegram,
        pause_on_mismatch=args.pause_on_mismatch,
    )
    print(json.dumps(report.to_jsonable(), indent=2, default=str))
    return 0 if report.sync_status != "failed" else 1


__all__ = [
    "ManualPositionRecord",
    "SyncReport",
    "sync_binance",
    "SYNCED_BINANCE",
    "MANUAL_POSITIONS",
]


if __name__ == "__main__":
    sys.exit(main())
