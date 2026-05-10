"""Telegram bot command list — registered with `setMyCommands` on bot init.

This is the contract between the user's Telegram chat and the agency.
``scripts/telegram_bot.py`` reads this list and routes each command to the
appropriate handler.
"""

from __future__ import annotations

# Ordering here is the order the commands appear in the Telegram client UI.
TELEGRAM_COMMANDS: list[dict[str, str]] = [
    {"command": "start",     "description": "Show bot status and command list"},
    {"command": "help",      "description": "Show available commands"},
    {"command": "status",    "description": "Show system status"},
    {"command": "mode",      "description": "Show current paper/live mode"},
    {"command": "paper",     "description": "Request paper mode"},
    {"command": "live",      "description": "Run live readiness check"},
    {"command": "scan",      "description": "Run market scan"},
    {"command": "positions", "description": "Show open positions"},
    {"command": "sync",      "description": "Sync Binance positions"},
    {"command": "summary",   "description": "Show latest summary"},
    {"command": "pause",     "description": "Pause new trades"},
    {"command": "resume",    "description": "Resume trading if safe"},
    {"command": "close",     "description": "Request close for a symbol"},
    {"command": "emergency", "description": "Emergency shutdown"},
    {"command": "risk",      "description": "Show risk settings"},
    {"command": "pnl",       "description": "Show PnL summary"},
    {"command": "journal",   "description": "Show latest journal entries"},
    {"command": "ask",       "description": "Ask Claude/system a question"},
    {"command": "approve",   "description": "Approve pending action"},
    {"command": "reject",    "description": "Reject pending action"},
    {"command": "settings",  "description": "Show safe settings summary"},
]


# Map each command to the agent / module that should handle it. Used by
# ``telegram_bot.py`` to route incoming updates. Handlers are resolved
# lazily at runtime so the bot can run without every module imported.
COMMAND_HANDLERS: dict[str, str] = {
    "start":     "scripts.telegram_bot:handle_start",
    "help":      "scripts.telegram_bot:handle_help",
    "status":    "scripts.telegram_bot:handle_status",
    "mode":      "scripts.telegram_bot:handle_mode",
    "paper":     "scripts.telegram_bot:handle_paper",
    "live":      "scripts.telegram_bot:handle_live",
    "scan":      "scripts.telegram_bot:handle_scan",
    "positions": "scripts.telegram_bot:handle_positions",
    "sync":      "scripts.telegram_bot:handle_sync",
    "summary":   "scripts.telegram_bot:handle_summary",
    "pause":     "scripts.telegram_bot:handle_pause",
    "resume":    "scripts.telegram_bot:handle_resume",
    "close":     "scripts.telegram_bot:handle_close",
    "emergency": "scripts.telegram_bot:handle_emergency",
    "risk":      "scripts.telegram_bot:handle_risk",
    "pnl":       "scripts.telegram_bot:handle_pnl",
    "journal":   "scripts.telegram_bot:handle_journal",
    "ask":       "scripts.telegram_claude_bridge:handle_ask",
    "approve":   "scripts.telegram_bot:handle_approve",
    "reject":    "scripts.telegram_bot:handle_reject",
    "settings":  "scripts.telegram_bot:handle_settings",
}


__all__ = ["TELEGRAM_COMMANDS", "COMMAND_HANDLERS"]
