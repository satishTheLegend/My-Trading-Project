"""Telegram → Claude / agency free-form-message bridge.

Routes `/ask MESSAGE` from Telegram to the local agency. Phase 7 will hand
this off to an actual Claude SDK call; today it returns a structured response
the user can act on, plus delegates obvious read-only intents (positions,
status, mode) to the same handlers `telegram_bot.py` uses.

**Hard rule**: this bridge never executes a live order from free-form text.
The user must use the structured commands (/close, /pause, /emergency,
/approve) — those go through Safety → Risk → Execution like the CLI.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any

log = logging.getLogger(__name__)


# Heuristic intent map — kept tiny so it's predictable. Phase 7 swaps this
# out for actual LLM intent classification.
_INTENTS = {
    "status": ("status", "current status", "what's the status", "how are you doing", "agency status"),
    "positions": ("positions", "open positions", "what positions", "show positions"),
    "mode": ("mode", "what mode", "paper or live", "current mode"),
    "risk": ("risk", "risk settings", "what's the risk", "show risk"),
    "settings": ("settings", "config", "show config", "show settings"),
    "help": ("help", "what can you do", "commands"),
}


def handle_ask(message: str, *, chat_id: str) -> str:
    """Route a free-form `/ask` message.

    Returns a string reply. Never returns an action that fires a live order.
    """
    text = (message or "").strip().lower()
    if not text:
        return ("Usage: /ask MESSAGE\n\n"
                "I can answer status/positions/mode/risk/settings questions "
                "and route some queries through the Journal Agent.")

    for intent, phrases in _INTENTS.items():
        if any(p in text for p in phrases):
            return _route_to_intent(intent, chat_id=chat_id)

    # No clear intent → return structured guidance.
    return (
        "I parsed your message as free-form text. For safety, free-form chat "
        "cannot fire live trades. Try one of:\n"
        "  /status — see mode + safety + Telegram state\n"
        "  /positions — open positions (agency + manual)\n"
        "  /pause / /resume\n"
        "  /close SYMBOL — request a reduce-only close\n"
        "  /approve APRV-... or /reject APRV-...\n\n"
        f"(Phase 7 will route this to a Claude reasoning step. Until then, "
        f"your message is logged at chat {chat_id[:4]}…)"
    )


def _route_to_intent(intent: str, *, chat_id: str) -> str:
    # Lazy import — keeps this module's import graph small.
    from . import telegram_bot
    handler = {
        "status": telegram_bot.handle_status,
        "positions": telegram_bot.handle_positions,
        "mode": telegram_bot.handle_mode,
        "risk": telegram_bot.handle_risk,
        "settings": telegram_bot.handle_settings,
        "help": telegram_bot.handle_help,
    }[intent]
    return handler("", chat_id=chat_id)


__all__ = ["handle_ask"]
