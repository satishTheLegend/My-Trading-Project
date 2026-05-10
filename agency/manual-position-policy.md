# Manual Position Policy

The user may open Binance Futures positions manually outside the agency. The agency must detect and handle them safely.

## Detection

A manual position is detected when Binance shows an open position that:

- Is not present in `data/open-positions.json`, **or**
- Has no agency `proposal_id`, **or**
- Has no agency order record, **or**
- Was opened while the agency was paused / not running.

`scripts/binance_position_sync.py` performs this detection on every sync.

## Default Handling

By default:

- Monitor manual positions through the Watcher Agent.
- Notify Telegram on first detection and on status changes.
- Include manual positions in the agency's overall risk exposure.
- **Never** open a duplicate position on the same symbol.
- Do not auto-close unless config allows or emergency safety requires.

## Config Switches

```env
ALLOW_MANUAL_POSITION_MANAGEMENT=true   # default — monitor + recommend
ALLOW_AUTO_CLOSE_MANUAL_POSITIONS=false # default — ask before closing
```

If `ALLOW_AUTO_CLOSE_MANUAL_POSITIONS=true`, the Exit Agent may apply the standard exit logic (TP / SL / invalidation / trailing) to manual positions, same as agency-opened ones.

## Emergency Exception

Regardless of config, the Safety Agent may force-close a manual position if:

- Liquidation distance becomes dangerous (default ≤ 30%).
- Stop-loss / protection orders are missing and risk is rising.
- The user triggered `/emergency`.
- Account margin is at risk.

Telegram alert + journal entry are mandatory whenever a manual position is force-closed.

## Telegram Format

```text
⚠️ Manual Position Detected

Symbol: {symbol}
Side: {side}
Entry: {entry}
Quantity: {quantity}
Leverage: {leverage}
Unrealized PnL: {pnl}
Liquidation: {liquidation}
Agency managed: {agency_managed}

Recommended action: {recommended_action}
```
