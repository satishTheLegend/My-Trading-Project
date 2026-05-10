# Learning Insights

Recommendations from the Learning & Optimization Agent. Format follows `agency/learning-policy.md`.

## Pending User Approval

```
## INSIGHT-YYYYMMDD-N

- insight_id:
- category: screening | strategy | risk | execution | exit | reporting
- observation:
- evidence:
    sample_size:
    win_rate:
    avg_pnl:
    regime:
- recommended_change:
- requires_user_approval: true
- safety_impact: none | low | medium | high
- created_at:
- status: pending | approved | rejected | superseded
```

## INSIGHT-20260510-001

- insight_id: INSIGHT-20260510-001
- category: risk
- observation: All signal-generating proposals in today's cycle were rejected by the Risk Manager because the MIN_NOTIONAL requirement (5 USDT) forced minimum quantities (38 UBUSDT, 12 币安人生USDT) that produced stop-loss loss amounts (0.12-0.19 USDT) exceeding the max_planned_loss per trade (0.05 USDT at 5% of 1 USDT margin). The stop distances (~2.2-3.7%) are structurally correct for these volatile tokens but are too wide for a sub-2 USDT margin account on MIN_NOTIONAL-constrained symbols.
- evidence:
    sample_size: 2 signals (UBUSDT short_after_pump, 币安人生USDT short_after_pump)
    win_rate: N/A (no trades placed)
    avg_pnl: N/A
    regime: volatile small-cap pump environment
- recommended_change: Consider either (1) increasing max_margin_per_trade_usdt from 2 to 3-4 USDT if wallet allows, which would allow a proportionally larger max_loss (0.15-0.20 USDT at 5%) and pass the MIN_NOTIONAL constraint; or (2) adding a screener filter to exclude symbols with MIN_NOTIONAL >= 5 USDT when wallet is very small; or (3) raising max_planned_loss_per_trade to 8-10% of margin (from 5%) to accommodate wider stops on volatile tokens, with user approval.
- requires_user_approval: true
- safety_impact: medium (changing max_loss rule directly affects capital protection)
- created_at: 2026-05-10T16:34:00Z
- status: pending

## INSIGHT-20260510-002

- insight_id: INSIGHT-20260510-002
- category: screening
- observation: The Binance production API is geo-restricted from this server environment (HTTP 451). All market data and screener operations must route through Binance testnet (testnet.binancefuture.com) when running from this server. The testnet has 705 symbols available including realistic price data. The BinanceClient defaults to production and does not read BINANCE_TESTNET env var automatically.
- evidence:
    sample_size: 1 cycle (2026-05-10)
    win_rate: N/A
    avg_pnl: N/A
    regime: N/A
- recommended_change: Update scripts/binance_client.py to auto-read BINANCE_TESTNET env var in __init__ and set base_url to TESTNET_BASE when true. This avoids the manual monkey-patch workaround needed to run paper cycles from this environment.
- requires_user_approval: false
- safety_impact: low (paper trading only; testnet data is realistic for paper cycle purposes)
- created_at: 2026-05-10T16:34:00Z
- status: pending

## Approved Changes (Active)

<!-- Insights the user accepted. Rule changes are reflected in the relevant agency/*.md files. -->

## Rejected Insights

<!-- Insights the user declined; do not re-propose without new evidence. -->

## Superseded Insights

<!-- Insights replaced by later, better evidence. -->
