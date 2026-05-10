# Trade Journal

Authoritative record of every executed (or simulated, in PAPER_TRADING) trade. Append-only. The Journal & Accounting Agent owns this file.

## Trade Entry Format

```
## TRADE-YYYYMMDD-N

- proposal_id:
- mode: PAPER_TRADING | SEMI_AUTO_LIVE | FULL_AUTO_LIVE
- symbol:
- side: LONG | SHORT
- strategy:
- market_regime:
- entry_time:
- entry_price:
- quantity:
- leverage:
- margin_mode: ISOLATED | CROSS
- margin_usdt:
- notional_usdt:
- stop_loss:
- take_profit_targets: []
- exit_time:
- exit_price:
- exit_reason: tp_hit | partial_tp | stop_hit | invalidation_exit | trail_exit | emergency_exit | manual
- gross_pnl_usdt:
- fees_usdt:
- funding_usdt:
- slippage_usdt:
- net_pnl_usdt:
- max_favorable_pnl_usdt:
- max_adverse_pnl_usdt:
- mistake_tags: []
- lessons:
- order_ids: []
```

## Daily Aggregation Format

```
## DAY-yyyy-mm-dd

- trades: N
- wins: N
- losses: N
- win_rate: %
- gross_pnl_usdt:
- fees_usdt:
- funding_usdt:
- net_pnl_usdt:
- best_trade:
- worst_trade:
- regime_today:
- notes:
```

---

_New trades appended below. Never edit existing entries; corrections go in a follow-up entry referencing the original `proposal_id`._
