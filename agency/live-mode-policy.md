# Live Mode Policy

## Supported Modes

The system has two primary modes, controlled by the `MODE` environment variable:

- `paper`
- `live`

```bash
MODE=paper
MODE=live
```

If `MODE` is missing, empty, or anything other than `paper`/`live`, the system defaults to `paper`.

## Paper Mode

In paper mode:

- Do not place real Binance orders.
- Simulate entries and exits via `scripts/paper_execution.py`.
- Simulate fees, slippage, PnL, and position updates.
- Telegram updates are allowed.
- Binance market data may be used.
- Binance account reads may be used if credentials are configured, but no orders are placed.

## Live Mode

In live mode, real execution is possible only if **all** of the following are true:

1. `MODE=live`.
2. `ALLOW_LIVE_EXECUTION=true`.
3. `BINANCE_API_KEY` and `BINANCE_API_SECRET` are set in environment variables only (never in code, never in memory files, never in chat).
4. The API key has no withdrawal permission (verified via permission preflight).
5. Safety/Kill-Switch Agent allows trading (no pause, no breached caps).
6. Risk Manager Agent approves the exact trade.
7. Position Sizing Agent produces a valid Binance-filter-compliant quantity.
8. Execution Agent verifies symbol filters, leverage, margin mode, precision, and protective orders.
9. Wallet balance ≥ `MIN_WALLET_BALANCE_USDT`.
10. If `REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER=true`, Telegram is reachable and a confirmation came through.

If any condition fails, the cycle either falls back to paper mode or exits cleanly with `live-readiness-only` status. **Never** execute a live order on an unmet precondition.

## Mode Conflict Rule

If `MODE=live` but live safety is incomplete, the effective mode is `live-readiness-only`:

- Read account state, run reconciliation, run health checks.
- Do **not** place any orders.
- Surface the blocking conditions in the cycle report.

## Wallet-Based Trading

Trade size must be based on actual wallet balance, never on hardcoded notionals:

1. Read wallet balance from `/fapi/v2/account`.
2. Read available margin.
3. Apply `MAX_MARGIN_PER_TRADE_USDT` and `MAX_MARGIN_PER_TRADE_PERCENT` caps.
4. Apply `MAX_PLANNED_LOSS_PER_TRADE_MARGIN_PERCENT`.
5. Set leverage from risk math (volatility, liquidation distance), not greed.
6. Reject the trade if Binance's MIN_NOTIONAL forces an unsafe size.

## Manual Positions

If the user opens manual positions on Binance directly, the system must:

- Detect them via `scripts/binance_position_sync.py`.
- Mark `manual_origin=true`.
- Monitor via the Watcher Agent.
- Report on Telegram.
- Manage them only according to `agency/manual-position-policy.md`.

The agency must never ignore manual exposure.
