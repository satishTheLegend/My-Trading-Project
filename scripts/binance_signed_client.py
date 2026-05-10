"""HMAC-SHA256 signed Binance USDT-M Futures client.

This is the ONLY module in the agency that touches signed endpoints. Every
order, leverage change, margin-mode change, and account query goes through
here. Phase 4 wraps it in `live_execution.py`; Phase 5+ adds the orchestrator
plumbing.

Security posture
----------------
- API key + secret are read **only** from environment variables. They are
  never accepted as constructor arguments, never written to memory files,
  never logged, never echoed back in error messages.
- Defaults to **Binance Futures testnet** (`https://testnet.binancefuture.com`).
  Mainnet requires the explicit env var `BINANCE_LIVE=true`.
- Signed requests are blocked entirely until the caller has called
  `enable_signed_requests()` — this is the single chokepoint that the
  Safety Agent uses to gate live execution.
- When constructing log lines for failed signed calls, the query string
  with `signature=...` is redacted before any logging happens.

Reference test vector (from Binance docs):
  secret    = 2b5eb11e18796d12d88f13dc27dbbd02c2cc51ff7059765ed9821957d82bb4d9
  payload   = symbol=BTCUSDT&side=BUY&type=LIMIT&quantity=1&price=9000
              &timeInForce=GTC&recvWindow=5000&timestamp=1591702613943
  signature = 3c661234138461fcc7a7d8746c6558c9842d4e10870d2ecbedf7777cad694af9

`tests/test_binance_signed_client.py::test_signature_matches_binance_docs`
verifies our implementation against this exact vector.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .binance_client import BinanceAPIError, _exp_backoff, _parse_binance_error, _retry_after_seconds

log = logging.getLogger(__name__)

PROD_BASE = "https://fapi.binance.com"
TESTNET_BASE = "https://testnet.binancefuture.com"

# Names of env vars we read. Centralized so unit tests can monkeypatch them
# in one place.
ENV_API_KEY = "BINANCE_API_KEY"
ENV_API_SECRET = "BINANCE_API_SECRET"
ENV_LIVE = "BINANCE_LIVE"               # "true" → mainnet; default → testnet
ENV_BASE_OVERRIDE = "BINANCE_BASE_URL"  # explicit override beats both

DEFAULT_RECV_WINDOW_MS = 5000


class CredentialsMissingError(RuntimeError):
    pass


class SignedRequestsDisabledError(RuntimeError):
    pass


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def sign_payload(secret: str, payload: str) -> str:
    """Compute the lowercase-hex HMAC-SHA256 signature of ``payload`` using ``secret``.

    Pure function — exposed so tests can verify against Binance's published
    test vector without instantiating the client.
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _resolve_base_url() -> str:
    explicit = os.environ.get(ENV_BASE_OVERRIDE, "").strip()
    if explicit:
        return explicit.rstrip("/")
    if os.environ.get(ENV_LIVE, "").strip().lower() == "true":
        return PROD_BASE
    return TESTNET_BASE


def _redact(url: str) -> str:
    """Strip signature= from a URL for safe logging."""
    return re.sub(r"signature=[a-f0-9]+", "signature=<redacted>", url)


# ----------------------------------------------------------------------------
# Client
# ----------------------------------------------------------------------------


@dataclass
class SignedClient:
    """Minimal signed client. Construct, then call `enable_signed_requests()`
    after the Safety Agent has run its preflight checks.

    Attributes:
        base_url: defaults via env. Use ``BINANCE_LIVE=true`` for mainnet.
        recv_window_ms: per-request validity window.
        timeout_s: HTTP timeout.
        max_retries: retried only on 5xx and network errors.
    """

    base_url: str = field(default_factory=_resolve_base_url)
    recv_window_ms: int = DEFAULT_RECV_WINDOW_MS
    timeout_s: float = 10.0
    max_retries: int = 3
    user_agent: str = "binance-futures-ai-agency/0.4-signed"

    _signed_enabled: bool = False
    _server_time_offset_ms: int = 0      # serverTime - localTime, refreshed on demand
    _last_offset_refresh: float = 0.0

    # ------------------------------------------------------------------ control

    def enable_signed_requests(self) -> None:
        """Open the gate. The Safety Agent calls this only after permission
        checks pass. Until then every signed call raises
        ``SignedRequestsDisabledError``.
        """
        self._signed_enabled = True

    def disable_signed_requests(self, reason: str = "") -> None:
        log.warning("disabling signed requests: %s", reason or "no reason given")
        self._signed_enabled = False

    @property
    def is_signed_enabled(self) -> bool:
        return self._signed_enabled

    @property
    def is_mainnet(self) -> bool:
        return self.base_url.startswith(PROD_BASE)

    # ------------------------------------------------------------------ creds

    def _credentials(self) -> tuple[str, str]:
        key = os.environ.get(ENV_API_KEY, "").strip()
        secret = os.environ.get(ENV_API_SECRET, "").strip()
        if not key or not secret:
            raise CredentialsMissingError(
                f"set {ENV_API_KEY} and {ENV_API_SECRET} environment variables "
                f"(never pass them on the command line or in code)"
            )
        return key, secret

    # ------------------------------------------------------------------ time

    def refresh_server_time_offset(self) -> int:
        """Fetch /fapi/v1/time and store the offset. Returns the offset in ms.

        Public endpoint (no auth) so we can call it before signed requests
        are enabled. The offset is included in the timestamp of every signed
        request to keep us inside Binance's recvWindow.
        """
        url = self.base_url + "/fapi/v1/time"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        server_ms = int(data["serverTime"])
        local_ms = int(time.time() * 1000)
        self._server_time_offset_ms = server_ms - local_ms
        self._last_offset_refresh = time.monotonic()
        log.debug("server time offset = %dms (server %d, local %d)",
                  self._server_time_offset_ms, server_ms, local_ms)
        return self._server_time_offset_ms

    def _timestamp_ms(self) -> int:
        # Refresh the offset if it's been more than 5 minutes since last sync.
        if time.monotonic() - self._last_offset_refresh > 300:
            try:
                self.refresh_server_time_offset()
            except Exception as e:
                log.warning("failed to refresh server time offset: %r", e)
        return int(time.time() * 1000) + self._server_time_offset_ms

    # ------------------------------------------------------------------ signed call

    def signed_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make a signed request. Raises:
          - SignedRequestsDisabledError if the gate hasn't been opened.
          - CredentialsMissingError if env vars aren't set.
          - BinanceAPIError on a 4xx/5xx after retries.
        """
        if not self._signed_enabled:
            raise SignedRequestsDisabledError(
                "signed requests blocked — Safety Agent must call "
                "enable_signed_requests() after the preflight checks pass."
            )
        api_key, api_secret = self._credentials()

        all_params: dict[str, Any] = {}
        if params:
            for k, v in params.items():
                if v is None:
                    continue
                # Binance expects bool as 'true'/'false' lowercase strings.
                if isinstance(v, bool):
                    all_params[k] = "true" if v else "false"
                else:
                    all_params[k] = v
        all_params.setdefault("recvWindow", self.recv_window_ms)
        all_params["timestamp"] = self._timestamp_ms()

        # Stable parameter ordering keeps the signature deterministic for
        # tests; Binance accepts any order, but tests need a fixed shape.
        ordered = sorted(all_params.items())
        payload = urllib.parse.urlencode(ordered)
        signature = sign_payload(api_secret, payload)
        url = f"{self.base_url}{path}?{payload}&signature={signature}"

        return self._do_request(method, url, api_key)

    def public_request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        """Public (unsigned) request — provided so reconciliation code can use
        a single client. No API key sent.
        """
        from urllib.parse import urlencode
        url = self.base_url + path
        if params:
            cleaned = {k: v for k, v in params.items() if v is not None}
            if cleaned:
                url += "?" + urlencode(sorted(cleaned.items()))
        return self._do_request(method, url, api_key=None)

    # ------------------------------------------------------------------ HTTP

    def _do_request(self, method: str, url: str, api_key: str | None) -> Any:
        headers = {"User-Agent": self.user_agent}
        if api_key is not None:
            headers["X-MBX-APIKEY"] = api_key

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(url, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    body = resp.read()
                if not body:
                    return None
                return json.loads(body.decode("utf-8"))
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8")
                except Exception:
                    pass
                code, msg = _parse_binance_error(err_body)
                # 4xx (other than 429/418) are NOT retried — they're our bug.
                if e.code == 429 or e.code == 418 or 500 <= e.code < 600:
                    last_err = BinanceAPIError(e.code, code, msg, _redact(url))
                    backoff = _retry_after_seconds(getattr(e, "headers", None)) or _exp_backoff(attempt)
                    log.warning(
                        "transient %d on %s — retry %d/%d in %.2fs (code=%s msg=%r)",
                        e.code, _redact(url), attempt + 1, self.max_retries, backoff, code, msg,
                    )
                    time.sleep(backoff)
                    continue
                # Hard 4xx — never retry, never log full url
                raise BinanceAPIError(e.code, code, msg, _redact(url))
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_err = e
                backoff = _exp_backoff(attempt)
                log.warning(
                    "network error on %s — retry %d/%d in %.2fs (%s)",
                    _redact(url), attempt + 1, self.max_retries, backoff, e,
                )
                time.sleep(backoff)

        if isinstance(last_err, BinanceAPIError):
            raise last_err
        raise BinanceAPIError(0, None, f"network failure after {self.max_retries} retries: {last_err}", _redact(url))


__all__ = [
    "SignedClient",
    "CredentialsMissingError",
    "SignedRequestsDisabledError",
    "ENV_API_KEY", "ENV_API_SECRET", "ENV_LIVE", "ENV_BASE_OVERRIDE",
    "PROD_BASE", "TESTNET_BASE",
    "sign_payload",
]
