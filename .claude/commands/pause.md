---
description: Pause new trading immediately.
---

Use Safety/Kill-Switch Agent. CLI: `python -m scripts.run_safety_reset --pause --reason "..." [--until-minutes N]`.

Effect:

- New trades disabled.
- Existing positions still monitored by Watcher Agent.
- Emergency exits still allowed (Safety Agent override).

Notify Telegram with the Safety Pause template.
