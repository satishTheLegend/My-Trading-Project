# Telegram Message Templates

Reused by `scripts/telegram_notifier.py`. Keep them concise — Telegram messages cap at 4096 chars but most of these stay under 500.

## Trade Proposal

```text
🧠 Trade Proposal

Symbol: {symbol}
Side: {side}
Strategy: {strategy}
Confidence: {confidence}
Entry Zone: {entry_zone}
Stop/Inval: {stop_loss}
Targets: {take_profit_targets}
Market: {market_regime}
Risk Status: Pending

Reason:
{trade_reason}
```

## Risk Rejected

```text
⛔ Trade Rejected by Risk Manager

Symbol: {symbol}
Reason: {risk_reason}
Required Changes:
{required_changes}
```

## Entry Filled

```text
✅ Entry Filled

Symbol: {symbol}
Side: {side}
Entry: {entry_price}
Qty: {quantity}
Leverage: {leverage}
Margin: {margin}
Protection: {protection_status}
```

## Profit Protection

```text
🟢 Profit Protection Alert

Symbol: {symbol}
Current PnL: {pnl}
Max PnL: {max_pnl}
Action: {recommended_action}
Reason: {reason}
```

## Trade Closed

```text
📌 Trade Closed

Symbol: {symbol}
Side: {side}
Entry: {entry}
Exit: {exit}
Net PnL: {net_pnl}
Fees: {fees}
Funding: {funding}
Reason: {exit_reason}
Learning: {learning}
```

## Manual Position Detected

```text
⚠️ Manual Position Detected

Symbol: {symbol}
Side: {side}
Entry: {entry}
Qty: {quantity}
Leverage: {leverage}
Unrealized PnL: {pnl}
Liquidation: {liquidation}
Agency Managed: {agency_managed}

Recommended Action:
{recommended_action}
```

## Safety Pause

```text
🛑 Trading Paused

Reason: {reason}
New Trades: Disabled
Open Position Monitoring: Active
Emergency Exits: Allowed
```

## Daily Summary

```text
📊 Daily Summary — {date}

Trades: {trades_count}    Win rate: {win_rate}
Net PnL: {net_pnl} USDT  Fees: {fees}
Best: {best_trade}
Worst: {worst_trade}
Open: {open_count}    Manual: {manual_count}
Safety: {safety_state}
```
