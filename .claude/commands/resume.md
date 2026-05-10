---
description: Resume new trading only if safety checks pass.
---

Use Safety/Kill-Switch Agent. CLI: `python -m scripts.run_safety_reset --resume --reason "..."`.

Before resuming, the Safety Agent checks:

- API reachable?
- Data freshness?
- Daily loss state?
- Open position count?
- Telegram availability (if required)?
- Binance sync clean?

If any check fails, the agent reports the blocker and stays paused.

Notify Telegram on successful resume.
