"""Telegram command list + auth/routing in telegram_bot.

We don't hit Telegram's network — every reply path is exercised through
direct handler calls."""

from __future__ import annotations

import pytest

from scripts import telegram_bot
from scripts.telegram_commands import COMMAND_HANDLERS, TELEGRAM_COMMANDS


def test_command_list_has_all_required_commands():
    names = {c["command"] for c in TELEGRAM_COMMANDS}
    required = {
        "start", "help", "status", "mode", "paper", "live", "scan",
        "positions", "sync", "summary", "pause", "resume", "close",
        "emergency", "risk", "pnl", "journal", "ask", "approve", "reject",
        "settings",
    }
    assert required.issubset(names)


def test_command_list_under_telegram_cap():
    # Telegram caps setMyCommands at 100.
    assert len(TELEGRAM_COMMANDS) <= 100


def test_every_command_has_handler_route():
    handler_names = {c.split(":")[0] for c in COMMAND_HANDLERS.values()}
    for c in TELEGRAM_COMMANDS:
        assert c["command"] in COMMAND_HANDLERS, f"no handler for /{c['command']}"
    # Each handler module path must be import-resolvable.
    assert all(":" in v for v in COMMAND_HANDLERS.values())


# ---------------------------------------------------------------------------
# Direct handler returns
# ---------------------------------------------------------------------------


def test_handle_start_returns_command_list():
    out = telegram_bot.handle_start("", chat_id="1")
    assert "/status" in out
    assert "/help" in out


def test_handle_status_does_not_leak_secrets(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "leak-key")
    monkeypatch.setenv("BINANCE_API_SECRET", "leak-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "leak-token")
    out = telegram_bot.handle_status("", chat_id="1")
    assert "leak-key" not in out
    assert "leak-secret" not in out
    assert "leak-token" not in out


def test_handle_settings_omits_secrets(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "another-key")
    out = telegram_bot.handle_settings("", chat_id="1")
    assert "another-key" not in out
    assert "binance_credentials_present" in out


def test_handle_close_requires_symbol():
    assert "Usage" in telegram_bot.handle_close("", chat_id="1")


def test_handle_approve_requires_id():
    assert "Usage" in telegram_bot.handle_approve("", chat_id="1")


def test_handle_reject_requires_id():
    assert "Usage" in telegram_bot.handle_reject("", chat_id="1")
