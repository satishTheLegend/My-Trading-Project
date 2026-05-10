"""Environment loader.

Reads the agency's runtime configuration from environment variables. Returns
a typed `RuntimeEnv` dataclass with secrets redacted in any string form.

Hard rules:
  - Secrets (API key, secret, Telegram token) are loaded but never returned
    by ``to_jsonable()`` or ``__repr__``. They live only on the `secrets`
    sub-object, which has its own redacting repr.
  - Invalid / missing `MODE` always falls back to ``paper``.
  - Boolean env vars use the standard truthy set: "true"/"1"/"yes"/"on".
  - Numeric env vars fall back to documented defaults if missing/malformed.

This module replaces ad-hoc ``os.environ.get`` calls scattered around the
codebase. The signed client + telegram bot import from here so there's one
audited surface for env handling.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any


VALID_MODES = ("paper", "live")
TRUTHY = {"true", "1", "yes", "on"}


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in TRUTHY


def _str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _decimal(name: str, default: Decimal) -> Decimal:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return default


def _csv(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return tuple()
    return tuple(p.strip() for p in raw.split(",") if p.strip())


# ----------------------------------------------------------------------------
# Secrets sub-object (kept apart so the parent dataclass stays printable).
# ----------------------------------------------------------------------------


@dataclass
class _Secrets:
    binance_api_key: str = ""
    binance_api_secret: str = ""
    telegram_bot_token: str = ""

    def has_binance(self) -> bool:
        return bool(self.binance_api_key) and bool(self.binance_api_secret)

    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token)

    def __repr__(self) -> str:  # pragma: no cover — never used in logic
        return (
            "_Secrets("
            f"binance_api_key={'<set>' if self.binance_api_key else '<empty>'}, "
            f"binance_api_secret={'<set>' if self.binance_api_secret else '<empty>'}, "
            f"telegram_bot_token={'<set>' if self.telegram_bot_token else '<empty>'})"
        )


# ----------------------------------------------------------------------------
# Public RuntimeEnv
# ----------------------------------------------------------------------------


@dataclass
class RuntimeEnv:
    # Mode
    mode: str = "paper"
    allow_live_execution: bool = False

    # Binance
    binance_testnet: bool = True
    binance_require_no_withdraw_permission: bool = True
    binance_default_margin_mode: str = "ISOLATED"
    binance_default_leverage: int = 3
    binance_max_leverage: int = 5

    # Wallet / risk
    min_wallet_balance_usdt: Decimal = Decimal("5")
    max_margin_per_trade_percent: Decimal = Decimal("20")
    max_margin_per_trade_usdt: Decimal = Decimal("2")
    max_planned_loss_per_trade_margin_percent: Decimal = Decimal("5")
    daily_max_loss_percent: Decimal = Decimal("15")
    max_consecutive_losses: int = 3
    max_open_positions: int = 2

    # Telegram
    telegram_chat_id: str = ""
    telegram_allowed_chat_ids: tuple[str, ...] = field(default_factory=tuple)
    telegram_enable_long_polling: bool = True
    telegram_enable_webhook: bool = False
    telegram_webhook_url: str = ""

    # Claude bridge
    claude_control_mode: str = "local"
    claude_command_timeout_seconds: int = 120

    # Manual position policy
    allow_manual_position_management: bool = True
    allow_auto_close_manual_positions: bool = False

    # Confirmation policy
    require_telegram_confirmation_for_live_order: bool = False

    # Secrets (redacted in repr)
    secrets: _Secrets = field(default_factory=_Secrets)

    # ------- properties -------------------------------------------------

    @property
    def all_authorized_chat_ids(self) -> tuple[str, ...]:
        ids = list(self.telegram_allowed_chat_ids)
        if self.telegram_chat_id and self.telegram_chat_id not in ids:
            ids.append(self.telegram_chat_id)
        return tuple(ids)

    @property
    def has_binance_credentials(self) -> bool:
        return self.secrets.has_binance()

    @property
    def has_telegram_credentials(self) -> bool:
        return self.secrets.has_telegram() and bool(self.telegram_chat_id)

    # ------- serdes -----------------------------------------------------

    def to_jsonable(self) -> dict[str, Any]:
        """Safe-to-print representation. Secrets are redacted."""
        return {
            "mode": self.mode,
            "allow_live_execution": self.allow_live_execution,
            "binance_testnet": self.binance_testnet,
            "binance_require_no_withdraw_permission": self.binance_require_no_withdraw_permission,
            "binance_default_margin_mode": self.binance_default_margin_mode,
            "binance_default_leverage": self.binance_default_leverage,
            "binance_max_leverage": self.binance_max_leverage,
            "binance_credentials_present": self.has_binance_credentials,
            "min_wallet_balance_usdt": str(self.min_wallet_balance_usdt),
            "max_margin_per_trade_percent": str(self.max_margin_per_trade_percent),
            "max_margin_per_trade_usdt": str(self.max_margin_per_trade_usdt),
            "max_planned_loss_per_trade_margin_percent": str(self.max_planned_loss_per_trade_margin_percent),
            "daily_max_loss_percent": str(self.daily_max_loss_percent),
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_open_positions": self.max_open_positions,
            "telegram_credentials_present": self.has_telegram_credentials,
            "telegram_chat_id_present": bool(self.telegram_chat_id),
            "telegram_allowed_chat_ids_count": len(self.telegram_allowed_chat_ids),
            "telegram_enable_long_polling": self.telegram_enable_long_polling,
            "telegram_enable_webhook": self.telegram_enable_webhook,
            "telegram_webhook_url_set": bool(self.telegram_webhook_url),
            "claude_control_mode": self.claude_control_mode,
            "claude_command_timeout_seconds": self.claude_command_timeout_seconds,
            "allow_manual_position_management": self.allow_manual_position_management,
            "allow_auto_close_manual_positions": self.allow_auto_close_manual_positions,
            "require_telegram_confirmation_for_live_order": self.require_telegram_confirmation_for_live_order,
        }


# ----------------------------------------------------------------------------
# Loader
# ----------------------------------------------------------------------------


def load_env() -> RuntimeEnv:
    """Read every env var the agency cares about. Pure read — no side effects."""
    raw_mode = _str("MODE", "paper").lower()
    mode = raw_mode if raw_mode in VALID_MODES else "paper"

    return RuntimeEnv(
        mode=mode,
        allow_live_execution=_bool("ALLOW_LIVE_EXECUTION", False),

        binance_testnet=_bool("BINANCE_TESTNET", True),
        binance_require_no_withdraw_permission=_bool(
            "BINANCE_REQUIRE_NO_WITHDRAW_PERMISSION", True),
        binance_default_margin_mode=_str("BINANCE_DEFAULT_MARGIN_MODE", "ISOLATED"),
        binance_default_leverage=_int("BINANCE_DEFAULT_LEVERAGE", 3),
        binance_max_leverage=_int("BINANCE_MAX_LEVERAGE", 5),

        min_wallet_balance_usdt=_decimal("MIN_WALLET_BALANCE_USDT", Decimal("5")),
        max_margin_per_trade_percent=_decimal("MAX_MARGIN_PER_TRADE_PERCENT", Decimal("20")),
        max_margin_per_trade_usdt=_decimal("MAX_MARGIN_PER_TRADE_USDT", Decimal("2")),
        max_planned_loss_per_trade_margin_percent=_decimal(
            "MAX_PLANNED_LOSS_PER_TRADE_MARGIN_PERCENT", Decimal("5")),
        daily_max_loss_percent=_decimal("DAILY_MAX_LOSS_PERCENT", Decimal("15")),
        max_consecutive_losses=_int("MAX_CONSECUTIVE_LOSSES", 3),
        max_open_positions=_int("MAX_OPEN_POSITIONS", 2),

        telegram_chat_id=_str("TELEGRAM_CHAT_ID"),
        telegram_allowed_chat_ids=_csv("TELEGRAM_ALLOWED_CHAT_IDS"),
        telegram_enable_long_polling=_bool("TELEGRAM_ENABLE_LONG_POLLING", True),
        telegram_enable_webhook=_bool("TELEGRAM_ENABLE_WEBHOOK", False),
        telegram_webhook_url=_str("TELEGRAM_WEBHOOK_URL"),

        claude_control_mode=_str("CLAUDE_CONTROL_MODE", "local"),
        claude_command_timeout_seconds=_int("CLAUDE_COMMAND_TIMEOUT_SECONDS", 120),

        allow_manual_position_management=_bool("ALLOW_MANUAL_POSITION_MANAGEMENT", True),
        allow_auto_close_manual_positions=_bool("ALLOW_AUTO_CLOSE_MANUAL_POSITIONS", False),
        require_telegram_confirmation_for_live_order=_bool(
            "REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER", False),

        secrets=_Secrets(
            binance_api_key=_str("BINANCE_API_KEY"),
            binance_api_secret=_str("BINANCE_API_SECRET"),
            telegram_bot_token=_str("TELEGRAM_BOT_TOKEN"),
        ),
    )


__all__ = ["RuntimeEnv", "load_env", "VALID_MODES"]
