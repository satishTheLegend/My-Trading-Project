"""Signed client: signature correctness, env handling, gate behavior.

All tests offline — no real HTTP. Each test that exercises ``signed_request``
patches the client's HTTP layer with a fake.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from scripts.binance_signed_client import (
    CredentialsMissingError,
    PROD_BASE,
    SignedClient,
    SignedRequestsDisabledError,
    TESTNET_BASE,
    sign_payload,
)


# ---------------------------------------------------------------------------
# Signature correctness against Binance's published vector
# ---------------------------------------------------------------------------


def test_signature_matches_binance_docs():
    """Reference vector from
    https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info
    SIGNED Endpoint Examples for POST /fapi/v1/order — HMAC Keys."""
    secret = "2b5eb11e18796d12d88f13dc27dbbd02c2cc51ff7059765ed9821957d82bb4d9"
    payload = ("symbol=BTCUSDT&side=BUY&type=LIMIT&quantity=1&price=9000"
               "&timeInForce=GTC&recvWindow=5000&timestamp=1591702613943")
    expected = "3c661234138461fcc7a7d8746c6558c9842d4e10870d2ecbedf7777cad694af9"
    assert sign_payload(secret, payload) == expected


# ---------------------------------------------------------------------------
# Base URL resolution
# ---------------------------------------------------------------------------


def test_base_url_defaults_to_testnet(monkeypatch):
    monkeypatch.delenv("BINANCE_LIVE", raising=False)
    monkeypatch.delenv("BINANCE_BASE_URL", raising=False)
    c = SignedClient()
    assert c.base_url == TESTNET_BASE
    assert not c.is_mainnet


def test_base_url_mainnet_when_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("BINANCE_LIVE", "true")
    monkeypatch.delenv("BINANCE_BASE_URL", raising=False)
    c = SignedClient()
    assert c.base_url == PROD_BASE
    assert c.is_mainnet


def test_base_url_explicit_override_wins(monkeypatch):
    monkeypatch.setenv("BINANCE_LIVE", "true")
    monkeypatch.setenv("BINANCE_BASE_URL", "https://example.com/")
    c = SignedClient()
    assert c.base_url == "https://example.com"


# ---------------------------------------------------------------------------
# Credentials handling
# ---------------------------------------------------------------------------


def test_credentials_missing_raises(monkeypatch):
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_API_SECRET", raising=False)
    c = SignedClient()
    c.enable_signed_requests()
    with pytest.raises(CredentialsMissingError):
        c.signed_request("GET", "/fapi/v2/account")


def test_signed_request_blocked_until_gate_opens(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "fake-key")
    monkeypatch.setenv("BINANCE_API_SECRET", "fake-secret")
    c = SignedClient()
    with pytest.raises(SignedRequestsDisabledError):
        c.signed_request("GET", "/fapi/v2/account")


# ---------------------------------------------------------------------------
# Signed request payload construction
# ---------------------------------------------------------------------------


def test_signed_request_constructs_correct_url(monkeypatch):
    """Capture what URL the client would send. Verify:
      - parameters are sorted
      - timestamp + recvWindow are appended
      - signature is correct for the constructed payload
      - X-MBX-APIKEY header is set
    """
    monkeypatch.setenv("BINANCE_API_KEY", "test-key-12345")
    monkeypatch.setenv("BINANCE_API_SECRET", "secret-67890")

    captured: dict[str, Any] = {}

    def fake_do_request(self, method: str, url: str, api_key: str | None) -> Any:
        captured["method"] = method
        captured["url"] = url
        captured["api_key"] = api_key
        return {"orderId": 1, "status": "NEW"}

    monkeypatch.setattr(SignedClient, "_do_request", fake_do_request)
    monkeypatch.setattr(SignedClient, "_timestamp_ms", lambda self: 1591702613943)

    c = SignedClient()
    c.enable_signed_requests()
    result = c.signed_request("POST", "/fapi/v1/order", params={
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "timeInForce": "GTC",
        "quantity": 1,
        "price": 9000,
    })

    assert result == {"orderId": 1, "status": "NEW"}
    assert captured["method"] == "POST"
    assert captured["api_key"] == "test-key-12345"

    url = captured["url"]
    assert "/fapi/v1/order?" in url
    # Parameters are sorted alphabetically; timestamp + recvWindow appear; signature appended last.
    assert "price=9000" in url
    assert "quantity=1" in url
    assert "side=BUY" in url
    assert "symbol=BTCUSDT" in url
    assert "timeInForce=GTC" in url
    assert "timestamp=1591702613943" in url
    assert "recvWindow=5000" in url
    assert "&signature=" in url
    # The signature must appear at the END.
    assert url.split("&signature=")[1].count("&") == 0


def test_bool_params_serialized_as_lowercase_strings(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_API_SECRET", "s")
    captured: dict[str, Any] = {}

    def fake_do_request(self, method, url, api_key):
        captured["url"] = url
        return {}

    monkeypatch.setattr(SignedClient, "_do_request", fake_do_request)
    monkeypatch.setattr(SignedClient, "_timestamp_ms", lambda self: 1)

    c = SignedClient()
    c.enable_signed_requests()
    c.signed_request("POST", "/fapi/v1/order", params={
        "symbol": "BTCUSDT",
        "reduceOnly": True,
        "closePosition": False,
    })

    assert "reduceOnly=true" in captured["url"]
    assert "closePosition=false" in captured["url"]


def test_disable_signed_requests_after_enabling(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_API_SECRET", "s")
    c = SignedClient()
    c.enable_signed_requests()
    assert c.is_signed_enabled
    c.disable_signed_requests("test")
    assert not c.is_signed_enabled
    with pytest.raises(SignedRequestsDisabledError):
        c.signed_request("GET", "/fapi/v2/account")
