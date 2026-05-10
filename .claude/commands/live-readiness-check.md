---
description: Check whether live Binance Futures execution is safely allowed.
---

Run live readiness check using:

- Safety/Kill-Switch Agent
- Binance Sync Agent
- Risk Manager Agent
- Execution Agent
- Telegram Control Agent

Check:

1. `MODE=live`
2. `ALLOW_LIVE_EXECUTION=true`
3. `BINANCE_API_KEY` exists in environment (presence only — never echo the value)
4. `BINANCE_API_SECRET` exists in environment
5. No key is printed or stored
6. API key has no withdrawal permission (`/sapi/v1/account/apiRestrictions`)
7. Wallet balance ≥ `MIN_WALLET_BALANCE_USDT`
8. Risk config available
9. Telegram configured if `REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER=true`
10. Emergency close path exists (`scripts/run_emergency_close.py`)
11. Position sync works (`scripts/run_reconcile.py`)
12. Paper / testnet execution was tested OR user explicitly accepts risk

Return:

```json
{
  "live_ready": false,
  "blocking_issues": [],
  "warnings": [],
  "required_user_actions": []
}
```
