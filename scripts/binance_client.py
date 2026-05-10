"""Low-level Binance USDT-M Futures HTTP client.

PUBLIC endpoints only in Phase 2. Authenticated endpoints (account, orders)
arrive in Phase 4 inside a separate `binance_signed_client.py` so this file
can never accidentally place a live order.

Design choices
--------------
- Standard library only (urllib.request) — no third-party dependency required
  to run a paper cycle. Keeps the sandbox setup zero-friction.
- Tracks Binance's used-weight headers (`X-MBX-USED-WEIGHT-1M`) and pre-emptively
  sleeps when we get close to the per-minute weight cap. Going over the cap
  earns a 429 and then a 418 IP ban — both are unacceptable in a live agency.
- Exponential backoff on 5xx and 429 with jitter; honour `Retry-After` if present.
- Sane default timeout (10 s) — Binance public endpoints are usually <500 ms.
"""

from __future__ import annotations

import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# Production and testnet bases. Phase 2 uses production for read-only data
# (testnet's small-cap symbol set is too sparse to screen meaningfully).
PROD_BASE = "https://fapi.binance.com"
TESTNET_BASE = "https://testnet.binancefuture.com"

# Per-minute weight cap reported by exchangeInfo. Stay well under this.
DEFAULT_WEIGHT_CAP_PER_MIN = 2400
# Soft self-limit: pause when used weight crosses this fraction of the cap.
SOFT_WEIGHT_THRESHOLD = 0.85


class BinanceAPIError(RuntimeError):
    """Raised when Binance responds with an error payload."""

    def __init__(self, status: int, code: int | None, msg: str, url: str):
        self.status = status
        self.code = code
        self.msg = msg
        self.url = url
        super().__init__(f"HTTP {status} code={code} msg={msg!r} url={url}")


@dataclass
class BinanceClient:
    """Minimal public-data client for Binance USDT-M Futures.

    Usage::

        client = BinanceClient()
        info = client.get("/fapi/v1/exchangeInfo")

    Thread-safety: not safe for use from multiple threads. Construct one per
    worker. The agency only needs a single client per process.
    """

    base_url: str = PROD_BASE
    timeout_s: float = 10.0
    max_retries: int = 4
    user_agent: str = "binance-futures-ai-agency/0.2"
    weight_cap: int = DEFAULT_WEIGHT_CAP_PER_MIN

    # internal weight bookkeeping
    _used_weight_1m: int = 0
    _used_weight_window_started: float = field(default_factory=time.monotonic)

    # ----- public ----------------------------------------------------------

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a public endpoint. Returns parsed JSON.

        Raises:
            BinanceAPIError on non-2xx responses after retries are exhausted.
        """
        url = self._build_url(path, params)
        return self._request("GET", url)

    # ----- internals -------------------------------------------------------

    def _build_url(self, path: str, params: dict[str, Any] | None) -> str:
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        if params:
            # drop None values so callers can pass optional kwargs as `or None`
            cleaned = {k: v for k, v in params.items() if v is not None}
            if cleaned:
                url = url + "?" + urllib.parse.urlencode(cleaned)
        return url

    def _respect_weight_cap(self) -> None:
        """Sleep proactively if we've used most of the per-minute weight budget."""
        # The minute window resets server-side each minute. We approximate it
        # locally by tracking a 60s rolling start timestamp.
        elapsed = time.monotonic() - self._used_weight_window_started
        if elapsed >= 60:
            self._used_weight_1m = 0
            self._used_weight_window_started = time.monotonic()
            return
        if self._used_weight_1m >= self.weight_cap * SOFT_WEIGHT_THRESHOLD:
            sleep_for = max(0.0, 60.0 - elapsed) + random.uniform(0.05, 0.25)
            log.warning(
                "weight cap soft-limit hit (%d / %d); sleeping %.2fs",
                self._used_weight_1m, self.weight_cap, sleep_for,
            )
            time.sleep(sleep_for)
            self._used_weight_1m = 0
            self._used_weight_window_started = time.monotonic()

    def _record_weight(self, headers: Any) -> None:
        # Binance returns the weight used in the current minute on every response.
        # Header keys vary in case across CDNs, so search case-insensitively.
        if headers is None:
            return
        for k, v in headers.items():
            kl = k.lower()
            if kl == "x-mbx-used-weight-1m":
                try:
                    self._used_weight_1m = int(v)
                except (TypeError, ValueError):
                    pass
                return

    def _request(self, method: str, url: str) -> Any:
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._respect_weight_cap()
            req = urllib.request.Request(
                url, method=method, headers={"User-Agent": self.user_agent}
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    self._record_weight(resp.headers)
                    body = resp.read()
                if not body:
                    return None
                return json.loads(body.decode("utf-8"))
            except urllib.error.HTTPError as e:
                # Binance returns JSON error bodies even for 4xx/5xx.
                self._record_weight(getattr(e, "headers", None))
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8")
                except Exception:
                    pass
                code, msg = _parse_binance_error(err_body)
                # 429 = rate-limited, 418 = banned, 5xx = transient — retry.
                # 4xx (other) = client error, do NOT retry.
                if e.code == 429 or e.code == 418 or 500 <= e.code < 600:
                    last_err = BinanceAPIError(e.code, code, msg, url)
                    retry_after = _retry_after_seconds(getattr(e, "headers", None))
                    backoff = retry_after if retry_after is not None else _exp_backoff(attempt)
                    log.warning(
                        "transient %d on %s — retry %d/%d in %.2fs (code=%s msg=%r)",
                        e.code, url, attempt + 1, self.max_retries, backoff, code, msg,
                    )
                    time.sleep(backoff)
                    continue
                raise BinanceAPIError(e.code, code, msg, url)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_err = e
                backoff = _exp_backoff(attempt)
                log.warning(
                    "network error on %s — retry %d/%d in %.2fs (%s)",
                    url, attempt + 1, self.max_retries, backoff, e,
                )
                time.sleep(backoff)
        # exhausted retries
        if isinstance(last_err, BinanceAPIError):
            raise last_err
        raise BinanceAPIError(0, None, f"network failure after {self.max_retries} retries: {last_err}", url)


def _exp_backoff(attempt: int) -> float:
    # 0.5, 1.0, 2.0, 4.0... with jitter
    base = min(0.5 * (2 ** attempt), 8.0)
    return base + random.uniform(0.05, 0.25)


def _retry_after_seconds(headers: Any) -> float | None:
    if headers is None:
        return None
    for k, v in headers.items():
        if k.lower() == "retry-after":
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
    return None


def _parse_binance_error(body: str) -> tuple[int | None, str]:
    if not body:
        return None, ""
    try:
        d = json.loads(body)
    except ValueError:
        return None, body[:200]
    code = d.get("code") if isinstance(d, dict) else None
    msg = d.get("msg") if isinstance(d, dict) else None
    return code, msg or ""


__all__ = ["BinanceClient", "BinanceAPIError", "PROD_BASE", "TESTNET_BASE"]
