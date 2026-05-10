"""Binance account sync — thin convenience wrapper.

The full account-state functionality (balances, positions, permission
preflight) lives in `scripts/account.py`. This module is the literal
filename the upgrade-prompt folder layout asks for, exposing a stable
top-level surface for anyone scripting against ``binance_account_sync``.

If you're writing new code, prefer:

    from scripts.account import Account
    account = Account()
    balances = account.get_balances()
    positions = account.get_open_positions()
    perms = account.check_permissions()
"""

from __future__ import annotations

from .account import (
    Account,
    APIPermissionReport,
    ExchangePosition,
    FuturesBalance,
)
from .binance_signed_client import (
    SignedClient,
    SignedRequestsDisabledError,
)


def get_account_snapshot(account: Account | None = None) -> dict:
    """One-shot snapshot: balances + positions + permissions. JSON-friendly.

    Used by `/sync-binance` and `/status` for a single round trip when the
    caller wants everything at once.
    """
    account = account or Account()
    balances = account.get_balances()
    positions = account.get_open_positions()
    return {
        "balances": [
            {
                "asset": b.asset,
                "wallet_balance": str(b.wallet_balance),
                "available_balance": str(b.available_balance),
                "cross_un_pnl": str(b.cross_un_pnl),
            } for b in balances
        ],
        "positions": [
            {
                "symbol": p.symbol,
                "side": p.side,
                "quantity": str(p.quantity),
                "entry_price": str(p.entry_price),
                "mark_price": str(p.mark_price),
                "unrealized_pnl": str(p.un_realized_profit),
                "leverage": p.leverage,
                "margin_type": p.margin_type,
                "liquidation_price": str(p.liquidation_price) if p.liquidation_price else None,
            } for p in positions
        ],
    }


__all__ = [
    "Account",
    "APIPermissionReport",
    "ExchangePosition",
    "FuturesBalance",
    "SignedClient",
    "SignedRequestsDisabledError",
    "get_account_snapshot",
]
