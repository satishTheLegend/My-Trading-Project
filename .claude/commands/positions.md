---
description: Show agency and Binance-synced open positions.
---

Use Binance Sync Agent + Position Manager Agent.

Return:

- Agency positions (from `data/open-positions.json`)
- Manual positions (from `data/manual-positions.json`)
- Binance positions (from `data/synced-binance-positions.json`)
- Per-position: side, qty, leverage, entry, mark, unrealized PnL, liquidation, protection status (stop/TP present?)
- Recommended action (hold / take-profit / tighten stop / close / emergency)

Group by `agency_managed` so the user can tell at a glance which positions the agency is responsible for.
