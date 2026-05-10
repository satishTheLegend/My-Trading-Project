---
description: Show current agency status — mode, wallet, safety, Telegram, and positions.
---

Use User Report Agent + Binance Sync Agent + Safety Agent.

Return:

- Current mode (paper / live-readiness-only / live-enabled)
- Live execution allowed or blocked (with reasons)
- Wallet balance
- Open positions (agency-managed and manual, separately)
- Safety state (paused? reason? cooldown remaining?)
- Telegram state (initialized? commands registered? last send?)
- Last trade summary
- Any active warnings

Never echo any secret.
