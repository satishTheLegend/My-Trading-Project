---
description: Switch or inspect trading mode using MODE=paper or MODE=live safety rules.
---

Arguments:
`$ARGUMENTS`

Update or inspect runtime mode.

Rules:

- Valid modes: `paper`, `live`.
- Default to `paper` for any unrecognized value.
- `live` does NOT mean automatic execution unless `ALLOW_LIVE_EXECUTION=true`.
- Before switching to live, run `/live-readiness-check`.
- Never expose secrets in the response.

Implementation lives in `scripts/mode_manager.py`. The CLI form is:

```bash
python -m scripts.mode_manager --status
python -m scripts.mode_manager --set paper
python -m scripts.mode_manager --set live    # only changes mode-state.json; safety still gates
```

Return:

```json
{
  "requested_mode": "$ARGUMENTS",
  "effective_mode": "paper | live-readiness-only | live-enabled",
  "live_execution_allowed": false,
  "warnings": []
}
```
