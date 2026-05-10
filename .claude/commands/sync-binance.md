---
description: Sync Binance wallet, open positions, open orders, and manual positions.
---

Use the Binance Sync Agent. CLI: `python -m scripts.binance_position_sync`.

Sync:

- Wallet balance + available margin
- Open positions (`/fapi/v2/positionRisk`)
- Open orders (`/fapi/v1/openOrders`)
- Manual positions (no internal `proposal_id`)
- Position mismatches (delegates to `scripts/position_manager.py::reconcile`)

If manual positions are detected:

- Update `data/manual-positions.json` and `data/synced-binance-positions.json`.
- Notify Telegram via the post-detection template.
- Include in risk exposure (counts toward `max_open_positions`, blocks duplicate symbol).
- Start Watcher monitoring if `ALLOW_MANUAL_POSITION_MANAGEMENT=true`.

Return the standard `BinanceSyncAgent` output JSON.
