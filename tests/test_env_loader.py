"""env_loader: defaults + redaction + boolean parsing."""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.env_loader import VALID_MODES, load_env


def _clear(monkeypatch):
    for k in (
        "MODE", "ALLOW_LIVE_EXECUTION", "BINANCE_API_KEY", "BINANCE_API_SECRET",
        "BINANCE_TESTNET", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
        "TELEGRAM_ALLOWED_CHAT_IDS", "TELEGRAM_ENABLE_LONG_POLLING",
        "MIN_WALLET_BALANCE_USDT", "MAX_OPEN_POSITIONS",
        "ALLOW_MANUAL_POSITION_MANAGEMENT", "REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER",
    ):
        monkeypatch.delenv(k, raising=False)


def test_default_mode_is_paper(monkeypatch):
    _clear(monkeypatch)
    env = load_env()
    assert env.mode == "paper"
    assert env.allow_live_execution is False


def test_invalid_mode_falls_back_to_paper(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MODE", "wibble")
    env = load_env()
    assert env.mode == "paper"


def test_live_mode_recognized(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MODE", "live")
    env = load_env()
    assert env.mode == "live"


def test_truthy_boolean_parsing(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("ALLOW_LIVE_EXECUTION", "TRUE")
    env = load_env()
    assert env.allow_live_execution is True
    monkeypatch.setenv("ALLOW_LIVE_EXECUTION", "yes")
    env = load_env()
    assert env.allow_live_execution is True
    monkeypatch.setenv("ALLOW_LIVE_EXECUTION", "no")
    env = load_env()
    assert env.allow_live_execution is False


def test_credentials_present_flag(monkeypatch):
    _clear(monkeypatch)
    assert not load_env().has_binance_credentials
    monkeypatch.setenv("BINANCE_API_KEY", "K")
    monkeypatch.setenv("BINANCE_API_SECRET", "S")
    assert load_env().has_binance_credentials


def test_secrets_repr_redacts(monkeypatch):
    _clear(monkeypatch)
    # Use values that don't collide with field names in the redacted repr
    # (which mentions "token" in the field name `telegram_bot_token`).
    monkeypatch.setenv("BINANCE_API_KEY", "very-secret-key-xyz")
    monkeypatch.setenv("BINANCE_API_SECRET", "very-secret-secret-xyz")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "topsecret-bot-credential")
    env = load_env()
    repr_text = repr(env.secrets)
    assert "very-secret-key-xyz" not in repr_text
    assert "very-secret-secret-xyz" not in repr_text
    assert "topsecret-bot-credential" not in repr_text
    assert "<set>" in repr_text


def test_to_jsonable_does_not_leak_secrets(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("BINANCE_API_KEY", "leak-this-key")
    monkeypatch.setenv("BINANCE_API_SECRET", "leak-this-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "leak-this-token")
    env = load_env()
    payload = env.to_jsonable()
    text = repr(payload)
    assert "leak-this-key" not in text
    assert "leak-this-secret" not in text
    assert "leak-this-token" not in text
    assert payload["binance_credentials_present"] is True


def test_csv_parsing_for_allowed_chat_ids(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111, 222, ,333")
    env = load_env()
    assert env.telegram_allowed_chat_ids == ("111", "222", "333")


def test_authorized_chat_ids_includes_primary(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111,222")
    env = load_env()
    assert "999" in env.all_authorized_chat_ids
    assert "111" in env.all_authorized_chat_ids


def test_decimal_parsing(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MIN_WALLET_BALANCE_USDT", "12.5")
    env = load_env()
    assert env.min_wallet_balance_usdt == Decimal("12.5")


def test_decimal_falls_back_on_garbage(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MIN_WALLET_BALANCE_USDT", "not-a-number")
    env = load_env()
    assert env.min_wallet_balance_usdt == Decimal("5")


def test_int_falls_back_on_garbage(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MAX_OPEN_POSITIONS", "abc")
    env = load_env()
    assert env.max_open_positions == 2
