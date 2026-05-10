# data/

Runtime state files, written by agents during operation. Phase 1 ships with this directory empty; Phase 2+ populates it.

## Expected Files

- `agency-state.json` — current operating mode, last cycle timestamps.
- `system-health.json` — Safety Agent health snapshot.
- `open-positions.json` — Position Manager source of truth.
- `active-signals.json` — in-flight Trade Decision proposals.
- `risk-state.json` — Risk Manager rolling counters (daily PnL, consecutive losses).

These files contain NO secrets. API keys live only in environment variables (see `config/env.example`).
