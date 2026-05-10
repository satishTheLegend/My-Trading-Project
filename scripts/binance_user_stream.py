"""Binance user-data WebSocket stream — listenKey lifecycle + event router.

Phase 7+ feature. Today this module ships:
  - The signed `listenKey` create/keep-alive/close lifecycle (REST).
  - A minimal event-router skeleton.
  - A documented placeholder for the actual websocket loop.

Why the skeleton already?  Because the listenKey API is REST-signed and
relevant to live-mode safety (you must keep the listenKey alive every 30
minutes or the stream disconnects, and a dead stream means missed fill
notifications). The reconciliation loop in `position_manager.py` is the
backstop, but a live websocket dramatically tightens response time.

Do not enable this in PAPER mode — it has no value paper-side.

Lifecycle endpoints (USDT-M Futures):
  POST   /fapi/v1/listenKey   → create or refresh, returns listenKey
  PUT    /fapi/v1/listenKey   → keep alive (call every < 60 min)
  DELETE /fapi/v1/listenKey   → close

Event types we'll route in Phase 7:
  ACCOUNT_UPDATE      → balance + position changes
  ORDER_TRADE_UPDATE  → order events (filled, partial, canceled)
  ACCOUNT_CONFIG_UPDATE
  MARGIN_CALL
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from .binance_signed_client import (
    SignedClient,
    SignedRequestsDisabledError,
)

log = logging.getLogger(__name__)

LISTEN_KEY_PATH = "/fapi/v1/listenKey"


@dataclass
class ListenKey:
    listen_key: str
    created_at: str
    last_kept_alive_at: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "listen_key_present": bool(self.listen_key),
            "created_at": self.created_at,
            "last_kept_alive_at": self.last_kept_alive_at,
        }


def create_listen_key(client: SignedClient | None = None) -> ListenKey:
    """POST /fapi/v1/listenKey — returns a new listenKey for the account.

    The listenKey itself is a sensitive credential: anyone with it can
    subscribe to your account events. We never log it, never persist it,
    never include it in any to_jsonable output.
    """
    client = client or SignedClient()
    if not client.is_signed_enabled:
        raise SignedRequestsDisabledError(
            "binance_user_stream.create_listen_key called before signed gate opened"
        )
    # The listenKey endpoint requires only the API key, not a query signature,
    # but the SignedClient transparently adds the signature; Binance ignores
    # the redundant signature. Keep the call surface uniform with other
    # signed calls.
    resp = client.signed_request("POST", LISTEN_KEY_PATH)
    key = str(resp.get("listenKey", ""))
    if not key:
        raise RuntimeError("listenKey not returned by Binance")
    return ListenKey(listen_key=key, created_at=_now_iso())


def keep_alive(client: SignedClient | None = None) -> bool:
    """PUT /fapi/v1/listenKey — call at least every 30 minutes.

    Binance auto-expires listenKeys at 60 minutes; we call at 30 to be safe.
    """
    client = client or SignedClient()
    if not client.is_signed_enabled:
        raise SignedRequestsDisabledError("keep_alive called before signed gate opened")
    client.signed_request("PUT", LISTEN_KEY_PATH)
    return True


def close_listen_key(client: SignedClient | None = None) -> bool:
    client = client or SignedClient()
    if not client.is_signed_enabled:
        raise SignedRequestsDisabledError("close_listen_key called before signed gate opened")
    client.signed_request("DELETE", LISTEN_KEY_PATH)
    return True


# ----------------------------------------------------------------------------
# Event router (skeleton)
# ----------------------------------------------------------------------------


@dataclass
class EventRouter:
    handlers: dict[str, Callable[[dict[str, Any]], None]] = field(default_factory=dict)

    def on(self, event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self.handlers[event_type] = handler

    def dispatch(self, event: dict[str, Any]) -> None:
        et = event.get("e") or event.get("event_type")
        handler = self.handlers.get(et)
        if handler is None:
            log.debug("user-stream event %s with no handler", et)
            return
        try:
            handler(event)
        except Exception as e:
            log.exception("user-stream handler for %s raised: %r", et, e)


# ----------------------------------------------------------------------------
# Phase 7 stub — actual websocket loop
# ----------------------------------------------------------------------------


def run_stream(*, listen_key: ListenKey, router: EventRouter) -> None:
    """Connect to ``wss://fstream.binance.com/ws/<listenKey>``, dispatch events.

    Phase 7 will implement this with the standard library `websockets` package
    or `websocket-client`. Today this raises NotImplementedError to make any
    accidental "use it now" path loud.
    """
    raise NotImplementedError(
        "scripts.binance_user_stream.run_stream is a Phase 7 stub. "
        "Reconciliation loop in scripts.position_manager handles state drift "
        "in the meantime."
    )


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


__all__ = [
    "ListenKey",
    "EventRouter",
    "create_listen_key",
    "keep_alive",
    "close_listen_key",
    "run_stream",
]
