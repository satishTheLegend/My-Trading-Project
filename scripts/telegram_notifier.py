"""Telegram alert sender.

Stateless module — every function reads env on each call. If credentials are
missing or Telegram is unreachable, the function logs the failure and returns
False. **The agency cycle never fails because Telegram is down.**

Templates live in `agency/telegram-templates.md`. The functions here render
those templates with provided context and POST to Telegram's `sendMessage`
endpoint.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .env_loader import load_env

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
TELEGRAM_EVENTS = _PROJECT_ROOT / "data" / "telegram-events.jsonl"
TELEGRAM_API = "https://api.telegram.org"


def send_message(text: str, *, chat_id: str | None = None,
                 parse_mode: str | None = None) -> bool:
    """Low-level sendMessage. Returns True on 2xx, False otherwise.

    Failures are logged and journaled to ``data/telegram-events.jsonl`` but
    never raised — the agency must keep running even if Telegram is down.
    """
    env = load_env()
    if not env.has_telegram_credentials:
        _log_event({"kind": "send_skip", "reason": "telegram credentials missing"})
        return False

    target_chat = chat_id or env.telegram_chat_id
    if not target_chat:
        _log_event({"kind": "send_skip", "reason": "no chat id"})
        return False

    url = f"{TELEGRAM_API}/bot{env.secrets.telegram_bot_token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": target_chat,
        "text": text[:4000],   # Telegram caps at 4096; leave headroom
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
    except urllib.error.URLError as e:
        log.warning("telegram send failed: %r", e)
        _log_event({"kind": "send_failed", "error": str(e)})
        return False
    except Exception as e:
        log.warning("telegram send unexpected error: %r", e)
        _log_event({"kind": "send_failed", "error": repr(e)})
        return False

    _log_event({"kind": "send_ok" if ok else "send_failed",
                "chars": len(text)})
    return ok


# ----------------------------------------------------------------------------
# Templated alerts
# ----------------------------------------------------------------------------


def send_trade_proposal(proposal: dict[str, Any]) -> bool:
    text = (
        "🧠 Trade Proposal\n\n"
        f"Symbol: {proposal.get('symbol', '?')}\n"
        f"Side: {proposal.get('side', '?')}\n"
        f"Strategy: {proposal.get('strategy', '?')}\n"
        f"Confidence: {proposal.get('confidence', '?')}\n"
        f"Entry Zone: {proposal.get('entry_zone', '?')}\n"
        f"Stop/Inval: {proposal.get('stop_loss', '?')}\n"
        f"Targets: {proposal.get('take_profit_targets', '?')}\n"
        f"Market: {proposal.get('market_regime', '?')}\n"
        f"Risk Status: Pending\n\n"
        f"Reason:\n{proposal.get('trade_reason', '?')}"
    )
    return send_message(text)


def send_risk_rejected(symbol: str, risk_reason: str,
                       required_changes: list[str] | None = None) -> bool:
    rc = "\n".join(required_changes or []) or "—"
    text = (
        f"⛔ Trade Rejected by Risk Manager\n\n"
        f"Symbol: {symbol}\n"
        f"Reason: {risk_reason}\n"
        f"Required Changes:\n{rc}"
    )
    return send_message(text)


def send_entry_filled(fill: dict[str, Any]) -> bool:
    text = (
        f"✅ Entry Filled\n\n"
        f"Symbol: {fill.get('symbol', '?')}\n"
        f"Side: {fill.get('side', '?')}\n"
        f"Entry: {fill.get('entry_price', '?')}\n"
        f"Qty: {fill.get('quantity', '?')}\n"
        f"Leverage: {fill.get('leverage', '?')}\n"
        f"Margin: {fill.get('margin', '?')}\n"
        f"Protection: {fill.get('protection_status', '?')}"
    )
    return send_message(text)


def send_profit_protection_alert(advice: dict[str, Any]) -> bool:
    text = (
        f"🟢 Profit Protection Alert\n\n"
        f"Symbol: {advice.get('symbol', '?')}\n"
        f"Current PnL: {advice.get('pnl', '?')}\n"
        f"Max PnL: {advice.get('max_pnl', '?')}\n"
        f"Action: {advice.get('recommended_action', '?')}\n"
        f"Reason: {advice.get('reason', '?')}"
    )
    return send_message(text)


def send_trade_summary(trade: dict[str, Any]) -> bool:
    text = (
        f"📌 Trade Closed\n\n"
        f"Symbol: {trade.get('symbol', '?')}\n"
        f"Side: {trade.get('side', '?')}\n"
        f"Entry: {trade.get('entry', '?')}\n"
        f"Exit: {trade.get('exit', '?')}\n"
        f"Net PnL: {trade.get('net_pnl', '?')}\n"
        f"Fees: {trade.get('fees', '?')}\n"
        f"Funding: {trade.get('funding', '?')}\n"
        f"Reason: {trade.get('exit_reason', '?')}\n"
        f"Learning: {trade.get('learning', '—')}"
    )
    return send_message(text)


def send_manual_position_alert(position: dict[str, Any]) -> bool:
    rec = position.get("recommended_action", "Monitor; close manually if risk grows.")
    text = (
        f"⚠️ Manual Position Detected\n\n"
        f"Symbol: {position.get('symbol', '?')}\n"
        f"Side: {position.get('side', '?')}\n"
        f"Entry: {position.get('entry_price', '?')}\n"
        f"Qty: {position.get('quantity', '?')}\n"
        f"Leverage: {position.get('leverage', '?')}\n"
        f"Unrealized PnL: {position.get('unrealized_pnl', '?')}\n"
        f"Liquidation: {position.get('liquidation_price', '?')}\n"
        f"Agency Managed: {position.get('agency_managed', False)}\n\n"
        f"Recommended Action:\n{rec}"
    )
    return send_message(text)


def send_safety_pause(reason: str) -> bool:
    text = (
        f"🛑 Trading Paused\n\n"
        f"Reason: {reason}\n"
        f"New Trades: Disabled\n"
        f"Open Position Monitoring: Active\n"
        f"Emergency Exits: Allowed"
    )
    return send_message(text)


def send_error_alert(error: str, *, context: str = "") -> bool:
    text = f"⚠️ Error\n\n{error}"
    if context:
        text += f"\n\nContext: {context}"
    return send_message(text)


def send_safety_alert(alert: dict[str, Any]) -> bool:
    text = (
        f"🛡️ Safety Alert\n\n"
        f"Event: {alert.get('event_type', '?')}\n"
        f"Details: {alert.get('details', '?')}\n"
        f"Action: {alert.get('action_taken', '?')}"
    )
    return send_message(text)


def send_daily_summary(summary: dict[str, Any]) -> bool:
    text = (
        f"📊 Daily Summary — {summary.get('date', '?')}\n\n"
        f"Trades: {summary.get('trades_count', 0)}    "
        f"Win rate: {summary.get('win_rate', '?')}\n"
        f"Net PnL: {summary.get('net_pnl', '?')} USDT  "
        f"Fees: {summary.get('fees', '?')}\n"
        f"Best: {summary.get('best_trade', '—')}\n"
        f"Worst: {summary.get('worst_trade', '—')}\n"
        f"Open: {summary.get('open_count', 0)}    "
        f"Manual: {summary.get('manual_count', 0)}\n"
        f"Safety: {summary.get('safety_state', '?')}"
    )
    return send_message(text)


# ----------------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------------


def _log_event(event: dict[str, Any]) -> None:
    event = {**event, "ts": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"}
    try:
        TELEGRAM_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        with TELEGRAM_EVENTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError as e:
        log.debug("could not append telegram event: %r", e)


__all__ = [
    "send_message",
    "send_trade_proposal",
    "send_risk_rejected",
    "send_entry_filled",
    "send_profit_protection_alert",
    "send_trade_summary",
    "send_manual_position_alert",
    "send_safety_pause",
    "send_safety_alert",
    "send_error_alert",
    "send_daily_summary",
]
