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

**Session date:** 2026-05-10 (session 2)
**Session ID:** claude/sonnet-4-6-live-cycle-01
**Mode at session end:** live (BINANCE_TESTNET=false — mainnet env set; mainnet geo-blocked HTTP 451 from server IP; testnet HTTP 200 accessible)

### What was done this session (session 2)

1. **Full live-readiness-check and full workflow run** across all 15 agents:
   - ALL blocks from session 1 re-verified: BLOCK-001 CLEARED, BLOCK-002 CLEARED (data/manual-positions.json and synced positions both show empty arrays — no residual positions), BLOCK-003 CLEARED, BLOCK-004 CLEARED.
   - NEW BLOCK identified: BLOCK-006 — Binance mainnet API geo-restricted from this server (HTTP 451). `BINANCE_TESTNET=false` is set but mainnet endpoint unreachable. Testnet accessible (HTTP 200).
   - Safety state: `trading_paused=false`, 0 consecutive losses, 0 daily PnL, clean.
   - Mode resolution: `effective_mode=live-enabled` (code path passes) but actual API calls fail at network level.

2. **Full market intelligence cycle** completed using testnet public data:
   - BTC: 81359 USDT (+0.81% 24h) — neutral/sideways
   - ETH: 2354 USDT (+1.12% 24h) — neutral-bullish
   - Regime: VOLATILE (small-cap pump environment active)
   - 611 symbols scanned from testnet

3. **Token screening** completed:
   - 10 small-cap high-volume candidates identified
   - Top movers: PONKEUSDT +36%, HIPPOUSDT +32%, LAYERUSDT +27%, NAORISUSDT -25%

4. **Token research** completed on top 5 candidates with spread/funding/RSI analysis

5. **Strategy selection** — best setup identified: LAYERUSDT pullback_long
   - RSI 15m: 37.2 (oversold), spread: 8 bps (PASS), range position: 4.2% (at support)
   - Funding: -0.49% (longs receive payment — advantageous)

6. **Trade proposal** created: PROP-20260510-LAYERUSDT-001
   - Entry: 0.12550, Stop: 0.12274 (-2.2%), TP: 0.13102 (+4.4%)
   - Qty: 39.9 LAYER, Notional: 5.01 USDT, Margin: 1.67 USDT at 3x

7. **Risk Manager approval**: ALL 9 checks PASS (spread, stop, liquidation, notional, loss limit, RR, funding, consecutive losses, pause state)

8. **Safety Agent BLOCK**: mainnet API returns -2015 (geo-restricted). Live order cannot be placed.

9. **Trade rejected** — recorded in `memory/rejected-trades.md` as REJECTED-20260510-002

### What still needs attention

| Priority | Item | Required action |
|----------|------|-----------------|
| CRITICAL | BLOCK-006: Mainnet Binance API geo-restricted from server (HTTP 451) | Whitelist server IP in Binance API key settings, OR use a VPS/proxy in an allowed region, OR accept paper-only mode |
| MEDIUM | `symbol_filters.py`: PERCENT_PRICE filter parsed but not enforced | error-fix-agent should add enforcement |
| MEDIUM | Duplicate safety event IDs in `memory/safety-events.md` | error-fix-agent should add UUID-based IDs to emergency close script |
| LOW | `run_live_cycle.py`: no visible mainnet warning in cycle report | Add `report["warnings"].append("MAINNET ACTIVE")` when BINANCE_TESTNET=false |
| INFO | INSIGHT-20260510-001: max_margin_per_trade increase pending user decision | User to decide on raising max_margin to 3-4 USDT or raising max_loss% |

### Open positions (this session)

- Internal store (`data/open-positions.json`): does not exist (no positions)
- `data/manual-positions.json`: empty array — confirmed clean
- `data/synced-binance-positions.json`: empty array (synced at 17:22:57Z)
- Binance mainnet: cannot verify (API geo-blocked). Last known state: no positions from last emergency close attempts.

### Safety state at session end

```json
{
  "daily_pnl_usdt": "0",
  "consecutive_losses": 0,
  "trading_paused": false,
  "daily_period_start": ""
}
```

### Environment at session end

| Variable | Value |
|----------|-------|
| MODE | live |
| ALLOW_LIVE_EXECUTION | true |
| BINANCE_TESTNET | false (mainnet env — but mainnet HTTP 451 geo-blocked) |
| BINANCE_LIVE | NOT_SET (signed client defaults to testnet — this is CORRECT for safe signed calls) |
| TELEGRAM_BOT_TOKEN | SET |
| TELEGRAM_CHAT_ID | 8514713186 |
| BINANCE_API_KEY | SET (64 chars) |
| BINANCE_API_SECRET | SET (64 chars) |

### To start the next session cleanly

```bash
# OPTION A: Fix geo-restriction (recommended for live trading)
# 1. Log into Binance → API Management → your API key → IP restriction → add this server's IP
# 2. OR switch to a VPS in an allowed region
# 3. Then:
export BINANCE_TESTNET=false
export BINANCE_LIVE=true   # forces SignedClient to mainnet
python -m scripts.binance_position_sync  # verify zero positions
# Then run /live-trade-cycle

# OPTION B: Continue in paper mode (no API fix needed)
export MODE=paper
python -m scripts.run_paper_cycle
```

---

## Session History

| Date | Mode | Trades | Net PnL | Notes |
|------|------|--------|---------|-------|
| 2026-05-10 (1) | live/testnet | 0 | 0 USDT | Setup session — fixes applied, no trades executed |
| 2026-05-10 (2) | live/mainnet-blocked | 0 | 0 USDT | Full workflow run; LAYERUSDT long setup found; blocked by API geo-restriction |
