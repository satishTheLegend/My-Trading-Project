"""mode_manager: effective-mode resolution."""

from __future__ import annotations

import pytest

from scripts.env_loader import load_env
from scripts.mode_manager import (
    EFFECTIVE_LIVE_ENABLED, EFFECTIVE_LIVE_READINESS_ONLY, EFFECTIVE_PAPER,
    resolve_mode,
)


def _clear(monkeypatch):
    for k in (
        "MODE", "ALLOW_LIVE_EXECUTION",
        "BINANCE_API_KEY", "BINANCE_API_SECRET",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
        "REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER",
    ):
        monkeypatch.delenv(k, raising=False)


def test_paper_mode_resolves_to_paper(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MODE", "paper")
    r = resolve_mode()
    assert r.requested_mode == "paper"
    assert r.effective_mode == EFFECTIVE_PAPER
    assert r.live_execution_allowed is False


def test_invalid_mode_resolves_to_paper(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MODE", "garbage")
    r = resolve_mode()
    assert r.effective_mode == EFFECTIVE_PAPER


def test_live_without_allow_flag_is_readiness_only(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_EXECUTION", "false")
    monkeypatch.setenv("BINANCE_API_KEY", "K")
    monkeypatch.setenv("BINANCE_API_SECRET", "S")
    r = resolve_mode()
    assert r.effective_mode == EFFECTIVE_LIVE_READINESS_ONLY
    assert r.live_execution_allowed is False
    assert any("ALLOW_LIVE_EXECUTION=false" in b for b in r.blockers)


def test_live_without_credentials_is_readiness_only(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_EXECUTION", "true")
    # No API key/secret.
    r = resolve_mode()
    assert r.effective_mode == EFFECTIVE_LIVE_READINESS_ONLY
    assert any("BINANCE_API" in b for b in r.blockers)


def test_live_with_full_credentials_resolves_to_live_enabled(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_EXECUTION", "true")
    monkeypatch.setenv("BINANCE_API_KEY", "K")
    monkeypatch.setenv("BINANCE_API_SECRET", "S")
    r = resolve_mode()
    assert r.effective_mode == EFFECTIVE_LIVE_ENABLED
    assert r.live_execution_allowed is True
    assert r.blockers == ()


def test_live_with_telegram_required_but_missing_blocks(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MODE", "live")
    monkeypatch.setenv("ALLOW_LIVE_EXECUTION", "true")
    monkeypatch.setenv("BINANCE_API_KEY", "K")
    monkeypatch.setenv("BINANCE_API_SECRET", "S")
    monkeypatch.setenv("REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER", "true")
    # No telegram credentials.
    r = resolve_mode()
    assert r.effective_mode == EFFECTIVE_LIVE_READINESS_ONLY
    assert any("Telegram" in b for b in r.blockers)
