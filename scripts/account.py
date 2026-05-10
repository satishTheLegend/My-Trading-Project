"""Typed account snapshot + permission preflight.

Reads (signed):
  - GET /fapi/v2/account            → balances, totalMarginBalance, etc.
  - GET /fapi/v2/positionRisk       → live position state per symbol
  - GET /sapi/v1/account/apiRestrictions  → withdrawal permission probe
                                       (spot endpoint, same key)

If the API key has `enableWithdrawals=true`, every signed call from
`live_execution.py` is refused. The Safety Agent re-runs this preflight on
every cycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .binance_signed_client import (
    BinanceAPIError,
    SignedClient,
    SignedRequestsDisabledError,
)

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class FuturesBalance:
    asset: str
    wallet_balance: Decimal
    available_balance: Decimal
    cross_un_pnl: Decimal


@dataclass(frozen=True)
class ExchangePosition:
    """One row from /fapi/v2/positionRisk (one-way mode).

    `position_amt` is signed: +ve = LONG, -ve = SHORT, 0 = flat.
    """
    symbol: str
    position_amt: Decimal
    entry_price: Decimal
    mark_price: Decimal
    un_realized_profit: Decimal
    leverage: int
    margin_type: str          # "isolated" | "cross"
    isolated_wallet: Decimal
    liquidation_price: Decimal | None
    update_time_ms: int

    @property
    def side(self) -> str:
        if self.position_amt > 0:
            return "LONG"
        if self.position_amt < 0:
            return "SHORT"
        return "FLAT"

    @property
    def quantity(self) -> Decimal:
        return abs(self.position_amt)

    @property
    def is_open(self) -> bool:
        return self.position_amt != 0


@dataclass(frozen=True)
class APIPermissionReport:
    """Permission probe result.

    Phase 4 refuses to enable signed requests unless ``trading_enabled`` is
    True AND ``withdrawals_enabled`` is False. ``probed_via_spot_endpoint``
    will be False when the API key lacks spot permission — in that case we
    fall back to a conservative posture (still allow trading, but log the
    inability to verify withdrawal status).
    """
    api_key_present: bool
    trading_enabled: bool
    withdrawals_enabled: bool | None    # None = could not determine
    futures_enabled: bool | None
    ip_restrict: bool | None
    probed_via_spot_endpoint: bool
    raw: dict[str, Any]
    notes: tuple[str, ...]

    @property
    def is_safe_to_trade(self) -> bool:
        if not self.api_key_present:
            return False
        if not self.trading_enabled:
            return False
        # If we couldn't determine withdrawals, do not trade live.
        if self.withdrawals_enabled is None:
            return False
        if self.withdrawals_enabled:
            return False
        return True


# ----------------------------------------------------------------------------
# Account API
# ----------------------------------------------------------------------------


class Account:
    def __init__(self, client: SignedClient | None = None) -> None:
        self.client = client or SignedClient()

    # ------- balances + positions ------------------------------------

    def get_balances(self) -> list[FuturesBalance]:
        data = self.client.signed_request("GET", "/fapi/v2/account")
        out: list[FuturesBalance] = []
        for a in data.get("assets", []):
            try:
                out.append(FuturesBalance(
                    asset=a["asset"],
                    wallet_balance=Decimal(str(a.get("walletBalance", "0"))),
                    available_balance=Decimal(str(a.get("availableBalance", "0"))),
                    cross_un_pnl=Decimal(str(a.get("crossUnPnl", "0"))),
                ))
            except (KeyError, ValueError):
                continue
        return out

    def get_open_positions(self, symbol: str | None = None) -> list[ExchangePosition]:
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        data = self.client.signed_request("GET", "/fapi/v2/positionRisk", params=params or None)
        out: list[ExchangePosition] = []
        for p in data:
            try:
                amt = Decimal(str(p.get("positionAmt", "0")))
                liq = p.get("liquidationPrice")
                out.append(ExchangePosition(
                    symbol=p["symbol"],
                    position_amt=amt,
                    entry_price=Decimal(str(p.get("entryPrice", "0"))),
                    mark_price=Decimal(str(p.get("markPrice", "0"))),
                    un_realized_profit=Decimal(str(p.get("unRealizedProfit", "0"))),
                    leverage=int(p.get("leverage", 1)),
                    margin_type=str(p.get("marginType", "")).lower(),
                    isolated_wallet=Decimal(str(p.get("isolatedWallet", "0"))),
                    liquidation_price=Decimal(str(liq)) if liq not in (None, "", "0") else None,
                    update_time_ms=int(p.get("updateTime", 0)),
                ))
            except (KeyError, ValueError):
                continue
        # Drop FLAT entries — the user only cares about real positions.
        return [p for p in out if p.is_open]

    # ------- permission preflight ------------------------------------

    def check_permissions(self) -> APIPermissionReport:
        """Defensive permission probe.

        We always have a futures account-info call to confirm the key is
        valid for trading. The withdrawal-permission bit lives on the spot
        side (`/sapi/v1/account/apiRestrictions`), so we try that. If the
        key has no spot permission, the call 4xx's; we record that and
        treat it as "could not determine withdrawals".
        """
        notes: list[str] = []
        api_key_present = False
        trading_enabled = False
        withdrawals_enabled: bool | None = None
        futures_enabled: bool | None = None
        ip_restrict: bool | None = None
        raw: dict[str, Any] = {}

        # 1) Verify futures key works (and that signed gate is open).
        try:
            self.client.signed_request("GET", "/fapi/v2/account")
            api_key_present = True
            trading_enabled = True   # If account-info works, trading routes are reachable
        except SignedRequestsDisabledError:
            notes.append("signed gate not yet opened — call enable_signed_requests() first")
            return APIPermissionReport(
                api_key_present=False, trading_enabled=False,
                withdrawals_enabled=None, futures_enabled=None,
                ip_restrict=None, probed_via_spot_endpoint=False,
                raw={}, notes=tuple(notes),
            )
        except BinanceAPIError as e:
            notes.append(f"futures account probe failed: code={e.code} msg={e.msg}")
            return APIPermissionReport(
                api_key_present=False, trading_enabled=False,
                withdrawals_enabled=None, futures_enabled=None,
                ip_restrict=None, probed_via_spot_endpoint=False,
                raw={}, notes=tuple(notes),
            )

        # 2) Probe withdrawal permission via spot endpoint.
        try:
            data = self.client.signed_request("GET", "/sapi/v1/account/apiRestrictions")
            raw = data if isinstance(data, dict) else {}
            withdrawals_enabled = bool(data.get("enableWithdrawals", False))
            futures_enabled = bool(data.get("enableFutures", True))
            ip_restrict = bool(data.get("ipRestrict", False))
            probed = True
        except BinanceAPIError as e:
            notes.append(
                f"could not probe spot apiRestrictions (code={e.code} msg={e.msg}); "
                "treating withdrawal permission as UNKNOWN — trading will be refused."
            )
            probed = False

        if withdrawals_enabled is True:
            notes.append(
                "API KEY HAS WITHDRAWAL PERMISSION ENABLED — refusing to trade. "
                "Disable withdrawals in your Binance API key settings, then retry."
            )

        return APIPermissionReport(
            api_key_present=api_key_present,
            trading_enabled=trading_enabled,
            withdrawals_enabled=withdrawals_enabled,
            futures_enabled=futures_enabled,
            ip_restrict=ip_restrict,
            probed_via_spot_endpoint=probed,
            raw=raw,
            notes=tuple(notes),
        )


__all__ = [
    "FuturesBalance",
    "ExchangePosition",
    "APIPermissionReport",
    "Account",
]
