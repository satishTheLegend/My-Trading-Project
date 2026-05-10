# Session Context Log

This file is written at the end of every Claude Code session and read at the
start of the next one. It gives the agency instant situational awareness
without re-running all agents from scratch.

---

## How to Use

On session start, Claude reads this file as part of the `SessionStart` hook.
It tells the orchestrator:
- What happened in the last session
- What is currently open
- What was decided and why
- What still needs attention

Agents that read this file: agency-orchestrator, safety-kill-switch-agent,
watcher-agent, position-manager-agent, user-report-agent.

---

## Latest Session Summary

**Session date:** 2026-05-10
**Session ID:** claude/relaxed-sagan-A9Lwo
**Mode at session end:** live (BINANCE_TESTNET=true — testnet routing active)

### What was done this session

1. **Live-readiness-check** completed across 5 agents:
   - Safety/Kill-Switch Agent: `trading_allowed=false` — BLOCK-001 (missing risk-state.json) and BLOCK-002 (unverified residual positions from prior emergency closes) identified.
   - Risk Manager Agent: BLOCK-004 — risk-config.example.json missing 4 fields.
   - Execution Agent: BLOCK-003 — ALLOW_LIVE_EXECUTION gate not wired into entrypoints.
   - Telegram Agent: OK — BOT_TOKEN and CHAT_ID both SET.
   - Binance Sync Agent: MODE=live, ALLOW_LIVE_EXECUTION=true, BINANCE_TESTNET=true.

2. **Fixes applied this session** (by error-fix-agent pattern):
   - `scripts/run_live_cycle.py`: Added `load_env()` import + `ALLOW_LIVE_EXECUTION` check before `enable_signed_requests()` (BLOCK-003).
   - `scripts/run_full_auto_cycle.py`: Same fix (BLOCK-003).
   - `config/risk-config.example.json`: Added `max_leverage`, `daily_max_loss_pct`, `max_consecutive_losses`, `max_open_positions` (BLOCK-004).
   - `data/risk-state.json`: Initialized via `run_safety_reset --reset-daily` (BLOCK-001).

3. **New agents created:**
   - `.claude/agents/error-fix-agent.md` — guest agent for code defect detection and repair.

### What still needs attention

| Priority | Item | Required action |
|----------|------|-----------------|
| HIGH | BLOCK-002: Unverified residual positions (DOGEUSDT, SHIBUSDT, MYSTERYUSDT) | Check Binance web UI or set `BINANCE_TESTNET=false` + run `/sync-binance` |
| HIGH | BLOCK-005: `BINANCE_TESTNET=true` — mainnet creds fail testnet auth (HTTP 401) | Set `BINANCE_TESTNET=false` in environment for mainnet live trading |
| MEDIUM | `symbol_filters.py`: PERCENT_PRICE filter parsed but not enforced | error-fix-agent should add enforcement in next session |
| MEDIUM | Duplicate safety event IDs in `memory/safety-events.md` | error-fix-agent should add UUID-based IDs to emergency close script |
| LOW | `run_live_cycle.py`: no visible mainnet warning in cycle report | Add `report["warnings"].append("MAINNET ACTIVE")` when BINANCE_TESTNET=false |

### Open positions (last known state)

- Internal store (`data/open-positions.json`): unknown — Binance sync failed due to 401.
- Manual positions: unknown — sync blocked.
- Recommendation: **verify zero open positions on Binance web UI before enabling mainnet.**

### Safety state at session end

```json
{
  "daily_pnl_usdt": "0",
  "consecutive_losses": 0,
  "trading_paused": false,
  "daily_period_start": "2026-05-10"
}
```

### Environment at session end

| Variable | Value |
|----------|-------|
| MODE | live |
| ALLOW_LIVE_EXECUTION | true |
| BINANCE_TESTNET | true (CHANGE TO false FOR MAINNET) |
| BINANCE_LIVE | NOT_SET |
| TELEGRAM_BOT_TOKEN | SET |
| TELEGRAM_CHAT_ID | SET |
| BINANCE_API_KEY | SET |
| BINANCE_API_SECRET | SET |

### To start the next session cleanly

```bash
# 1. Confirm zero open positions on Binance web UI
# 2. Switch to mainnet
export BINANCE_TESTNET=false
# 3. Resume session
claude
# 4. Then run:
/sync-binance          # verify positions
/live-readiness-check  # confirm all blocks cleared
/live-trade-cycle      # start live trading
```

---

## Session History

| Date | Mode | Trades | Net PnL | Notes |
|------|------|--------|---------|-------|
| 2026-05-10 | live/testnet | 0 | 0 USDT | Setup session — fixes applied, no trades executed |
