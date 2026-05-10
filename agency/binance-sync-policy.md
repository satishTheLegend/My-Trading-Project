# Binance Sync Policy

The system must keep internal state synchronized with the exchange before and during trading.

## Sync Required Before

- New trade decision
- Risk approval
- Position sizing
- Execution
- Monitoring tick
- Exit
- Telegram status report

## Sync Sources

`scripts/binance_position_sync.py` and `scripts/binance_account_sync.py` fetch:

- Wallet balance
- Available margin
- Open positions (`/fapi/v2/positionRisk`)
- Open orders (`/fapi/v1/openOrders`)
- Position side, entry price, quantity, leverage, margin mode
- Unrealized PnL
- Liquidation price
- Stop-loss / protection orders
- Take-profit orders

## Manual Position Detection

A manual position is any Binance open position that:

- Exists on Binance but not in `data/open-positions.json`, **or**
- Has no internal `proposal_id`, **or**
- Was opened outside agency execution.

When detected, the Binance Sync Agent:

1. Adds an entry to `data/manual-positions.json`.
2. Updates `data/synced-binance-positions.json`.
3. Marks `manual_origin=true` and `agency_managed=false`.
4. Notifies the Telegram Control Agent.
5. If `ALLOW_AUTO_CLOSE_MANUAL_POSITIONS=false` (default), prompts the user instead of acting.
6. If `ALLOW_AUTO_CLOSE_MANUAL_POSITIONS=true`, the Watcher and Exit Agents may manage it under strict safety rules.

## Manual Position Safety

Manual positions must not be ignored. The agency must:

- Monitor PnL, liquidation distance, and protection.
- Watch for BTC/ETH danger.
- Alert the user.
- Recommend exit when invalidation hits or risk grows.
- Auto-close only if policy allows or the Safety Agent declares emergency.

## Reconciliation

Internal state must reconcile with Binance state. On mismatch (`scripts/position_manager.py::reconcile`):

- Pause new trades.
- Alert the Safety Agent.
- Alert Telegram.
- Fix state before further execution.

A persistent mismatch flagged `pause_carry_over_rollover=true` survives the daily UTC rollover until manually resolved.
