# Execution Errors

Log of every Binance API error, partial fill anomaly, stop-placement failure, precision issue, or unexpected exchange response.

## Format

```
## ERROR-YYYYMMDD-N

- timestamp:
- mode:
- symbol:
- attempted_action: set_leverage | set_margin_mode | place_entry | place_stop | place_tp | reduce_only_close | cancel | other
- binance_code:
- binance_message:
- internal_state:
- exchange_state:
- impact: blocked_entry | open_without_protection | duplicate_position | reconciliation_required | cosmetic
- resolution:
- escalated_to: safety-agent | risk-manager | user | none
```

Never include API keys or secrets in this file.
