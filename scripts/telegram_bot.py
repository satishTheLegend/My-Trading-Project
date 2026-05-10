"""Telegram bot — long-polling controller + command router.

Reads commands from authorized Telegram chats and routes them to the
appropriate handler. Each handler returns a string that the bot replies with.

Hard rules:
  - Unknown chat IDs are rejected silently (logged but not replied to).
  - Bot token is never echoed.
  - Commands that ultimately place real orders go through the same Safety →
    Risk → Execution chain as the CLI — there is no fast path.
  - If Telegram is down, the bot logs and exits cleanly.

Usage::

    # Register commands + start long polling:
    python -m scripts.telegram_bot --register --poll

    # Just register:
    python -m scripts.telegram_bot --register

    # One poll cycle (handy for testing):
    python -m scripts.telegram_bot --poll-once
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .env_loader import load_env
from .telegram_commands import COMMAND_HANDLERS, TELEGRAM_COMMANDS
from .telegram_notifier import TELEGRAM_API, send_message

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
TELEGRAM_STATE = _PROJECT_ROOT / "data" / "telegram-state.json"
TELEGRAM_EVENTS = _PROJECT_ROOT / "data" / "telegram-events.jsonl"


# ----------------------------------------------------------------------------
# Public API for the rest of the agency
# ----------------------------------------------------------------------------


def register_commands() -> bool:
    """Call setMyCommands so the Telegram client shows the menu."""
    env = load_env()
    if not env.has_telegram_credentials:
        log.info("telegram credentials missing; skipping setMyCommands")
        return False
    url = f"{TELEGRAM_API}/bot{env.secrets.telegram_bot_token}/setMyCommands"
    payload = {"commands": json.dumps(TELEGRAM_COMMANDS)}
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
    except Exception as e:
        log.warning("setMyCommands failed: %r", e)
        return False
    _update_state({"commands_registered": ok})
    return ok


def get_me() -> dict[str, Any] | None:
    env = load_env()
    if not env.has_telegram_credentials:
        return None
    url = f"{TELEGRAM_API}/bot{env.secrets.telegram_bot_token}/getMe"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.warning("getMe failed: %r", e)
        return None


# ----------------------------------------------------------------------------
# Long polling
# ----------------------------------------------------------------------------


def poll_once(timeout_s: int = 25) -> int:
    """One getUpdates call → route + reply to each authorized message.

    Returns the number of updates handled.
    """
    env = load_env()
    if not env.has_telegram_credentials:
        log.info("telegram credentials missing; nothing to poll")
        return 0

    state = _load_state()
    offset = int(state.get("long_polling_offset") or 0)

    url = f"{TELEGRAM_API}/bot{env.secrets.telegram_bot_token}/getUpdates"
    params = {"timeout": timeout_s, "offset": offset}
    full = url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(full, timeout=timeout_s + 5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.warning("getUpdates failed: %r", e)
        return 0

    if not data.get("ok"):
        return 0

    handled = 0
    last_update_id = offset
    for update in data.get("result", []):
        last_update_id = max(last_update_id, int(update.get("update_id", 0)) + 1)
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            continue
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = msg.get("text", "") or ""
        _handle(env, chat_id, text)
        handled += 1

    _update_state({
        "long_polling_offset": last_update_id,
        "last_recv_at": _now_iso(),
    })
    return handled


def _handle(env, chat_id: str, text: str) -> None:
    if chat_id not in env.all_authorized_chat_ids:
        _log_event({"kind": "unauthorized", "chat_id_prefix": chat_id[:4], "text_len": len(text)})
        # Don't reveal anything to unauthorized chats — log only.
        return

    cmd, _, args = text.strip().partition(" ")
    if not cmd.startswith("/"):
        # Free-form message → treat as `/ask`.
        cmd = "/ask"
        args = text.strip()

    name = cmd.lstrip("/").split("@", 1)[0].lower()
    handler_path = COMMAND_HANDLERS.get(name)
    if handler_path is None:
        send_message(f"Unknown command: /{name}\n\nUse /help to see what I support.",
                     chat_id=chat_id)
        return

    try:
        handler = _resolve_handler(handler_path)
        reply = handler(args, chat_id=chat_id)
    except Exception as e:
        log.exception("handler %s raised", handler_path)
        reply = f"⚠️ Handler error: {type(e).__name__}: {e}"

    if reply:
        send_message(reply, chat_id=chat_id)
    _log_event({"kind": "cmd", "name": name, "chat_id_prefix": chat_id[:4]})


def _resolve_handler(path: str) -> Callable[..., str]:
    module_name, _, func_name = path.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, func_name)


# ----------------------------------------------------------------------------
# Default command handlers
# ----------------------------------------------------------------------------


def handle_start(_args: str, *, chat_id: str) -> str:
    cmds = "\n".join(f"/{c['command']} — {c['description']}" for c in TELEGRAM_COMMANDS)
    return f"🤖 Binance Futures AI Trading Agency\n\nMode: paper\n\n{cmds}"


def handle_help(_args: str, *, chat_id: str) -> str:
    return handle_start(_args, chat_id=chat_id)


def handle_status(_args: str, *, chat_id: str) -> str:
    env = load_env()
    safe = env.to_jsonable()
    summary = (
        f"📍 Status\n"
        f"Mode: {safe['mode']}    live_allowed: {env.allow_live_execution}\n"
        f"Binance creds: {'✅' if safe['binance_credentials_present'] else '❌'}    "
        f"Testnet: {safe['binance_testnet']}\n"
        f"Telegram creds: {'✅' if safe['telegram_credentials_present'] else '❌'}\n"
        f"Open positions cap: {safe['max_open_positions']}    "
        f"Daily loss cap: {safe['daily_max_loss_percent']}%\n"
        f"(use /sync for live position state)"
    )
    return summary


def handle_mode(_args: str, *, chat_id: str) -> str:
    from .mode_manager import resolve_mode
    r = resolve_mode()
    return (
        f"Mode: {r.requested_mode} → effective: {r.effective_mode}\n"
        f"Live allowed: {r.live_execution_allowed}\n"
        + ("Blockers:\n  - " + "\n  - ".join(r.blockers) if r.blockers else "No blockers.")
    )


def handle_paper(_args: str, *, chat_id: str) -> str:
    return ("To switch to paper, set MODE=paper in your environment and re-run. "
            "Telegram alone cannot override env-driven config.")


def handle_live(_args: str, *, chat_id: str) -> str:
    return ("To switch to live, set MODE=live AND ALLOW_LIVE_EXECUTION=true in your env, "
            "then run `/live-readiness-check` (or `python -m scripts.mode_manager --status`). "
            "Telegram alone cannot enable live mode.")


def handle_scan(_args: str, *, chat_id: str) -> str:
    return ("Scan must be run from the host: `python -m scripts.run_paper_cycle --top 3 --save`. "
            "Telegram-initiated scans land in Phase 7.")


def handle_positions(_args: str, *, chat_id: str) -> str:
    from .positions_store import PositionsStore
    open_p = PositionsStore().load_open()
    if not open_p:
        return "No agency-managed open positions. Use /sync to refresh from Binance."
    lines = ["📂 Open positions"]
    for p in open_p:
        lines.append(
            f"{p.symbol} {p.side} qty={p.quantity} entry={p.entry_price} "
            f"stop={p.stop_loss} unreal_pnl={p.unrealized_pnl}"
        )
    return "\n".join(lines)


def handle_sync(_args: str, *, chat_id: str) -> str:
    return ("Running sync requires the signed client (Binance creds in env). "
            "Use `python -m scripts.binance_position_sync --notify-telegram` from the host. "
            "Manual positions detected during that run will alert this chat automatically.")


def handle_summary(_args: str, *, chat_id: str) -> str:
    return ("Latest summary lives in `memory/trade-journal.md`. "
            "Use `python -m scripts.run_learning_report` for an aggregated view.")


def handle_pause(args: str, *, chat_id: str) -> str:
    from .safety_state import SafetyStateManager
    SafetyStateManager().pause(args or "telegram /pause")
    return "🛑 Trading paused. Existing positions are still monitored."


def handle_resume(args: str, *, chat_id: str) -> str:
    from .safety_state import SafetyStateManager
    SafetyStateManager().resume(manual=True)
    return "▶️ Resume requested. Next cycle will re-check safety before any trade fires."


def handle_close(args: str, *, chat_id: str) -> str:
    sym = args.strip().upper()
    if not sym:
        return "Usage: /close SYMBOL"
    return (f"Close request for {sym} acknowledged. Run "
            f"`python -m scripts.run_emergency_close --i-understand --reason 'telegram close {sym}'` "
            "from the host to actually fire (or wire scripts/run_close_position.py for symbol-scoped close).")


def handle_emergency(_args: str, *, chat_id: str) -> str:
    return ("⚠️ Emergency close from Telegram requires running "
            "`python -m scripts.run_emergency_close --i-understand` on the host. "
            "Telegram does not auto-fire emergency closes (single confirmation point).")


def handle_risk(_args: str, *, chat_id: str) -> str:
    env = load_env()
    return (
        f"Risk caps:\n"
        f"  max_margin_per_trade_usdt: {env.max_margin_per_trade_usdt}\n"
        f"  max_planned_loss_per_trade (% of margin): {env.max_planned_loss_per_trade_margin_percent}\n"
        f"  daily_max_loss_percent: {env.daily_max_loss_percent}\n"
        f"  max_consecutive_losses: {env.max_consecutive_losses}\n"
        f"  max_open_positions: {env.max_open_positions}"
    )


def handle_pnl(_args: str, *, chat_id: str) -> str:
    return ("Use `python -m scripts.run_learning_report` for full PnL breakdown. "
            "A Telegram-native PnL summary lands in Phase 7.")


def handle_journal(_args: str, *, chat_id: str) -> str:
    return ("Journal entries are in `memory/trade-journal.md`. "
            "Send a request via `/ask` and I'll route it to the Journal Agent.")


def handle_approve(args: str, *, chat_id: str) -> str:
    from .pending_approvals import PendingApprovalsStore
    aid = args.strip()
    if not aid:
        return "Usage: /approve APRV-..."
    a = PendingApprovalsStore().transition(aid, to="approved", notes="approved via telegram")
    if a is None:
        return f"No pending approval with id {aid}."
    return f"✅ Approved {aid}. Next live cycle will fire it."


def handle_reject(args: str, *, chat_id: str) -> str:
    from .pending_approvals import PendingApprovalsStore
    parts = args.strip().split(maxsplit=1)
    aid = parts[0] if parts else ""
    reason = parts[1] if len(parts) > 1 else "rejected via telegram"
    if not aid:
        return "Usage: /reject APRV-... reason"
    a = PendingApprovalsStore().transition(aid, to="rejected", notes=reason)
    if a is None:
        return f"No pending approval with id {aid}."
    return f"⛔ Rejected {aid}."


def handle_settings(_args: str, *, chat_id: str) -> str:
    env = load_env()
    safe = env.to_jsonable()
    # Only safe-to-share fields:
    keys = (
        "mode", "allow_live_execution", "binance_testnet",
        "binance_default_margin_mode", "binance_default_leverage", "binance_max_leverage",
        "min_wallet_balance_usdt", "max_margin_per_trade_usdt",
        "daily_max_loss_percent", "max_consecutive_losses", "max_open_positions",
        "binance_credentials_present", "telegram_credentials_present",
        "allow_manual_position_management", "allow_auto_close_manual_positions",
        "require_telegram_confirmation_for_live_order",
    )
    return "Settings:\n" + "\n".join(f"  {k}: {safe.get(k)}" for k in keys)


# ----------------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------------


def _load_state() -> dict[str, Any]:
    if not TELEGRAM_STATE.exists():
        return {}
    try:
        return json.loads(TELEGRAM_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _update_state(updates: dict[str, Any]) -> None:
    state = _load_state()
    state.update(updates)
    state["last_send_at"] = state.get("last_send_at") or _now_iso()
    TELEGRAM_STATE.parent.mkdir(parents=True, exist_ok=True)
    TELEGRAM_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _log_event(event: dict[str, Any]) -> None:
    event = {**event, "ts": _now_iso()}
    try:
        TELEGRAM_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        with TELEGRAM_EVENTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Telegram bot for the trading agency")
    p.add_argument("--register", action="store_true", help="setMyCommands")
    p.add_argument("--poll", action="store_true", help="long-poll loop")
    p.add_argument("--poll-once", action="store_true", help="single getUpdates call")
    p.add_argument("--get-me", action="store_true", help="call getMe (verifies token)")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    env = load_env()
    if not env.has_telegram_credentials:
        print(json.dumps({"error": "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set"}, indent=2))
        return 1

    if args.get_me:
        info = get_me()
        # Strip the username/id for safety; only return success.
        print(json.dumps({
            "getMe_ok": bool(info and info.get("ok")),
        }, indent=2))

    if args.register:
        ok = register_commands()
        print(json.dumps({"commands_registered": ok}, indent=2))

    if args.poll_once:
        n = poll_once()
        print(json.dumps({"updates_handled": n}, indent=2))

    if args.poll:
        log.info("starting Telegram long-poll loop (Ctrl-C to stop)")
        try:
            while True:
                poll_once()
        except KeyboardInterrupt:
            return 0

    return 0


__all__ = [
    "register_commands",
    "get_me",
    "poll_once",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
