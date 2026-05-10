# Binance Sync Memory

## Remember

- Last successful sync time.
- Last wallet balance.
- Last known open positions.
- Manual positions detected (with first-seen timestamp).
- State mismatches (kind, symbol, resolution).
- Reconciliation errors.
- Binance API read errors.

## Never store

- `BINANCE_API_KEY`.
- `BINANCE_API_SECRET`.
- Any credential.

## Auto-learning

- Learn recurring sync errors.
- Learn symbols that frequently mismatch due to precision/order behaviour.
- Recommend safer reconciliation frequency.
