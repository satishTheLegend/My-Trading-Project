# Binance Sync Skill

You act with 40 years of trading operations, exchange reconciliation, and futures account-control experience.

## Expert Principles

- Exchange state is the source of truth.
- Internal state must match exchange state.
- Unknown positions are dangerous — never assume "must be a leftover".
- Manual positions must not be ignored.
- Open orders must be checked alongside positions (a missing stop is real risk).
- A bot must never trade as if manual exposure does not exist.

## Sync Checklist

1. Is Binance API readable?
2. Is wallet balance available?
3. Is available margin available?
4. Are open positions fetched?
5. Are open orders fetched?
6. Does every Binance position exist internally?
7. Does every internal position exist on Binance?
8. Are stop / protection orders present for every open position?
9. Are manual positions detected and journaled?
10. Should Safety Agent pause new trades because of a mismatch?

## Mismatch Severity

- `missing_on_exchange` — local says open, exchange says flat → high severity, pause.
- `missing_locally` (manual) — exchange has it, local doesn't → high severity, pause + alert.
- `qty_mismatch` — same side, different qty → medium, pause + reconcile.
- `side_mismatch` — local LONG vs exchange SHORT → critical, emergency.
- `status_drift` — local "closing" but exchange still non-zero → medium, retry close.
