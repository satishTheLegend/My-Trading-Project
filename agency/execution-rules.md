# Execution Rules

## Binance API Security

- Store API key and secret in environment variables only.
- Never hardcode keys.
- Never print keys.
- Never commit keys.
- API key must not have withdrawal permission.
- If withdrawal permission exists, pause system.

## Required Environment Variables

Use examples only, never real secrets:

```bash
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_TESTNET=true
TRADING_MODE=PAPER_TRADING
```

## Live Order Requirements

Before order:

1. Confirm mode.
2. Confirm Safety approval.
3. Confirm Risk approval.
4. Confirm symbol tradeable.
5. Confirm leverage.
6. Confirm margin mode.
7. Confirm precision.
8. Confirm minimum notional.
9. Confirm quantity.
10. Confirm stop/protection.
11. Confirm no duplicate position.

After order:

1. Confirm status.
2. Confirm fill.
3. Confirm average price.
4. Confirm quantity.
5. Confirm stop/protection.
6. Update Position Manager.
7. Start Watcher Agent.

## Exit Requirements

- Use reduce-only.
- Confirm close.
- Confirm final PnL.
- Confirm position no longer open.
- Journal result.
