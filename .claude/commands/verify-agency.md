---
description: Verify the Binance Futures AI Trading Agency requirements and fix missing files.
---

Run full agency verification.

Read:
- `CLAUDE.md`
- `agency/`
- `.claude/agents/`
- `.claude/commands/`
- `agents/`
- `config/`
- `scripts/`
- `data/`

Verify:
1. All 16 required agents exist (orchestrator, market-intel, screener, research, strategy, decision, risk-manager, sizing, execution, position-manager, watcher, exit, journal, learning, safety, user-report) — plus the upgrade agents `telegram-control-agent` and `binance-sync-agent`.
2. Each agent has `agent.md`, `memory.md`, `skill.md`.
3. Safety rules + risk rules + execution rules exist.
4. Live mode policy + Telegram policy + Binance sync policy + Manual position policy + Profit protection policy exist.
5. Default mode is `paper` in `data/agency-state.json` and `data/mode-state.json`.
6. No secrets are committed (grep for `BINANCE_API_KEY=...` non-empty values, `TELEGRAM_BOT_TOKEN=...` etc).
7. Live execution is gated by both `MODE=live` AND `ALLOW_LIVE_EXECUTION=true`.

Fix missing safe files. Return verification JSON:

```json
{
  "verification_status": "complete | incomplete_fixed | incomplete_needs_user",
  "missing_files_created": [],
  "files_updated": [],
  "safety_issues_fixed": [],
  "remaining_user_actions": []
}
```
