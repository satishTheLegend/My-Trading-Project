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

**Session date:** 2026-05-10 (updated — full 15-step live workflow run)
**Session ID:** claude/session_01Nrt7RDq2rLiBTTJAxUU3JZ
**Mode at session end:** SEMI_AUTO_LIVE — hard blocks prevented execution (see below)

### What was done this session

1. **Full 15-step SEMI_AUTO_LIVE workflow executed** by Agency Orchestrator.

2. **All 15 agents consulted** in correct authority order:
   - Step 1 Safety: Clean counters, but BLOCK-002 (residual positions) and BLOCK-GEO (geo-restriction) identified.
   - Step 2 Market Intelligence: BTC ~80,600-81,000, mixed/consolidating, altcoin rotation index 45/100, futures OI declining.
   - Step 3 Token Screener: PONKEUSDT (Tier 1), UBUSDT (Tier 2), HIPPOUSDT excluded (spread 32 bps).
   - Step 4 Token Research: BLOCKED — mainnet API returns HTTP 451 geo-restriction. Live candle/funding data unavailable.
   - Step 5 Strategy: NO_TRADE — cannot score strategies without live data.
   - Step 6 Trade Decision: NO TRADE issued. 0 proposals.
   - Step 7 Risk Manager: Standby. INSIGHT-20260510-001 still pending (MIN_NOTIONAL vs 2 USDT wallet).
   - Step 8 Position Sizing: Not required.
   - Step 9 Execution: HARD BLOCK. Four simultaneous blocks. No orders attempted.
   - Step 10 Position Manager: No internal positions. Mainnet state unknown.
   - Step 11 Watcher: Idle.
   - Step 12 Journal: DAY-2026-05-10 cycle entry appended to trade-journal.md.
   - Step 13 Learning: INSIGHT-20260510-003 (geo-restriction + env mismatch) and INSIGHT-20260510-004 (MYSTERYUSDT residual) added.
   - Step 14 User Report: Compiled in Orchestrator final output.
   - Step 15 Session Context: This update.

3. **Critical new finding this session:**
   - Binance MAINNET (fapi.binance.com) returns HTTP 451 geo-restriction from this server.
   - This is a hard infrastructure block — no live mainnet orders can be placed from this server.
   - Testnet (testnet.binancefuture.com) IS reachable and functions correctly.
   - The environment still has BINANCE_TESTNET=true which routes all signed calls to testnet.
   - Mainnet API keys return code=-2015 on testnet.

### What still needs attention

| Priority | Item | Required action |
|----------|------|-----------------|
| CRITICAL | Binance mainnet HTTP 451 geo-restriction | Server cannot reach fapi.binance.com. All live trading on mainnet is impossible from this server. User must either: (a) use testnet with testnet API keys, or (b) deploy agency on a non-restricted server/VPN, or (c) use a different execution method. |
| HIGH | BLOCK-002: MYSTERYUSDT residual position unverified | Check Binance web UI — if no MYSTERYUSDT position exists, record as false alarm. If it does exist, close manually. |
| HIGH | BINANCE_TESTNET=true env still active | If using testnet: get testnet API keys from testnet.binancefuture.com. If going mainnet: change server/VPN. |
| MEDIUM | INSIGHT-20260510-001: MIN_NOTIONAL vs wallet constraint | User decision needed: raise max_margin to 3-4 USDT, or raise max_loss_pct to 8-10%, or add MIN_NOTIONAL screener filter. |
| MEDIUM | INSIGHT-20260510-002: BinanceClient BINANCE_TESTNET auto-read | Low-risk code improvement. Can be applied without user approval. |
| MEDIUM | symbol_filters.py: PERCENT_PRICE filter not enforced | error-fix-agent improvement. |
| LOW | Duplicate safety event IDs in safety-events.md | Cosmetic fix — add UUID-based IDs to emergency close script. |

### Open positions (last known state)

- Internal store (`data/open-positions.json`): DOES NOT EXIST — no positions tracked internally.
- `data/pending-approvals.json`: DOES NOT EXIST — no queued approvals.
- Mainnet positions: UNKNOWN — API geo-restricted (HTTP 451).
- MYSTERYUSDT: UNKNOWN — multiple close attempts failed. User must check Binance Web UI manually.
- Recommendation: Before ANY new session, manually verify zero open positions on Binance web UI or mobile app.

### Safety state at session end

```json
{
  "daily_pnl_usdt": "0",
  "consecutive_losses": 0,
  "trades_today": 0,
  "trading_paused": false,
  "daily_period_start": "2026-05-10"
}
```

### Environment at session end

| Variable | Value |
|----------|-------|
| MODE | live |
| ALLOW_LIVE_EXECUTION | true |
| BINANCE_TESTNET | true (routes to testnet.binancefuture.com) |
| TELEGRAM_BOT_TOKEN | SET |
| TELEGRAM_CHAT_ID | SET |
| BINANCE_API_KEY | SET (mainnet keys — fail on testnet) |
| BINANCE_API_SECRET | SET (mainnet keys — fail on testnet) |

### To start the next session cleanly

```
OPTION A — Use Testnet (this server):
  1. Get testnet API keys from https://testnet.binancefuture.com
  2. Set BINANCE_API_KEY and BINANCE_API_SECRET to testnet keys
  3. Confirm BINANCE_TESTNET=true remains set
  4. Run: python -m scripts.run_safety_reset --status
  5. Verify MYSTERYUSDT on Binance web UI — record finding in safety-events.md
  6. Run: python -m scripts.run_live_cycle --i-understand-this-is-real-money --reconcile-first --verbose

OPTION B — Use Mainnet (different server):
  1. Deploy agency on a server not geo-restricted by Binance (non-US, non-sanctioned region)
  2. Set BINANCE_TESTNET=false
  3. Confirm mainnet API keys present
  4. Verify MYSTERYUSDT on Binance web UI
  5. Run: python -m scripts.run_reconcile (should succeed)
  6. Run: python -m scripts.run_live_cycle --i-understand-this-is-real-money --reconcile-first --verbose
```

---

## Session History

| Date | Mode | Trades | Net PnL | Notes |
|------|------|--------|---------|-------|
| 2026-05-10 | live/testnet | 0 | 0 USDT | Setup session — fixes applied, no trades executed |
| 2026-05-10 | SEMI_AUTO_LIVE (blocked) | 0 | 0 USDT | Full 15-step workflow run. Hard blocks: mainnet HTTP 451 geo-restriction + env mismatch + MYSTERYUSDT residual. No orders placed. Capital safe. |
