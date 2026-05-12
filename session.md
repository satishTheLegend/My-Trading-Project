# SESSION MEMORY — Binance Futures AI Trading Agency

> **For new Claude Code sessions:** Skim this file first (≤ 2 min). Read in full ONLY if you're continuing live trading or debugging. Target: 5–7K tokens.

---

## 1. Current Operating Policy (LOCKED — do not change without user approval)

| Parameter | Value | Notes |
|---|---|---|
| Margin per trade | **3.5 USDT** | Sized for 8 slots × ~93% wallet deployment |
| Leverage | **2x–12x confidence-gated** (see ladder below) | User rule: "use leverage on confident trades only" |
| Max planned loss per trade | **0.50 USDT STRICT** | Round qty down if precision pushes loss > 0.50 |
| Min strategy confidence | **≥ 0.75** | Below this = NO TRADE |
| R:R measured at | **TP2** — required value scales with leverage tier (see ladder) | Engine TP1=1.5R, TP2=2.5R, TP3=4R |
| Exit plan | **33/33/33 scale at TP1/TP2/TP3 if MIN_NOTIONAL allows; else single TP at TP2** | TP1 placement is a policy breach unless infeasible |
| Daily loss cap | **4.0 USDT** (raised from 2.5 for 8-slot config) | Auto-pause new fires; existing SLs still run |
| Max open positions | **8** (raised from 5 by user 14:00Z) | No duplicate symbols |
| Per-cycle trade cap | **2** | Quality > volume |
| Decimal-priced tokens | **In scope** | BUSDT/SAGAUSDT/NAORISUSDT/QUSDT all traded |

**Confidence → Leverage → R:R ladder (user-locked 2026-05-11 14:10Z — leverage cap raised to 15x):**

| Confidence | Leverage | Notional/trade @ 3.5 margin | SL distance @ 0.50 loss | Required R:R-at-TP2 |
|---|---|---|---|---|
| 0.75–0.79 | 2x | 7.0 USDT | 7.1% | ≥ 2.0 |
| 0.80–0.84 | 3x | 10.5 USDT | 4.8% | ≥ 2.0 |
| 0.85–0.89 | 5x | 17.5 USDT | 2.9% | ≥ 2.5 |
| 0.90–0.94 | 8x | 28.0 USDT | 1.8% | ≥ 3.0 |
| ≥ 0.95 | **15x** (raised from 12x) | 52.5 USDT | 0.95% | ≥ 3.5 |

Higher leverage requires both higher conviction (confidence) AND higher upside (R:R) to justify the tighter stop. If a proposal's SL distance would be < 1.0% (noise-trigger risk), step DOWN one leverage tier even when confidence qualifies.

**Aggressive quick-profit exit rules (user-locked 2026-05-11 14:10Z) — applied by auto-adjust monitor every 5 min:**

| Trigger | Action |
|---|---|
| uPnL ≥ +2.0 USDT (hard cap) | EXIT 100% — lock the best case |
| MFE ≥ 1.0 USDT AND pullback ≥ 0.25 from MFE | EXIT 100% |
| MFE ≥ 0.50 USDT AND pullback ≥ 0.15 from MFE | EXIT 100% |
| MFE ≥ 0.30 USDT AND uPnL ≤ MFE × 0.20 (80% giveback) | EXIT 100% |

Plus existing SL trail rules (BE at 0.9R, lock 0.5R/1R/1.5R at 1.5/2/2.5R).

User intent: "we want profits not losses" — trade is for quick scalp wins, not deep swings. Trade-off: fewer big runners like the +1.25 FOLKSUSDT TP, more frequent small locked wins.

**User goal in their words:** *"all trades should take profit"*, *"we want profits not the losses"*, *"skip getting lose"*. Translation: tight quality gates, active loss management, profit-locking on winners.

---

## 2. Auto-management rules (locked, applied autonomously)

**Auto SL trail (every 5 min via cron):**
| r_curr reached | Action |
|---|---|
| ≥ 0.9R | Move SL to **breakeven** (= entry price) |
| ≥ 1.5R | Trail SL to lock **+0.5R** profit |
| ≥ 2.0R | Trail SL to lock **+1.0R** profit |
| ≥ 2.5R | Trail SL to lock **+1.5R** profit |

For LONG: `new_SL = entry + lock_R × (entry - original_SL)`. For SHORT: `new_SL = entry - lock_R × (original_SL - entry)`. Only TIGHTEN, never widen.

**Auto giveback protection (every 5 min):** if a position achieved a "huge lift" and gives most of it back, exit before the lift evaporates.
| MFE reached (max_favorable_pnl) | Current uPnL ≤ | Action |
|---|---|---|
| ≥ 1.0 USDT | 0.30 USDT | EXIT (reduce-only MARKET close) |
| ≥ 1.5 USDT | 0.50 USDT | EXIT (50%+ giveback from peak) |
| ≥ 2.5 USDT | MFE × 0.50 | EXIT (lock half the peak) |

**Auto R:R floor enforcement (every 5 min):** if a position's TP yields R:R < 2.0, cancel + replace at TP2-level (2.5R).

**Auto loss-research (every 10 min):** any position at r_curr ≤ -0.3R triggers token-research-agent. Returns HOLD / EXIT EARLY / REDUCE PARTIAL. Decisions auto-executed. History stored in `data/loss-research-log.jsonl` to avoid re-researching unchanged losers (30-min cooldown unless R worsens by ≥ 0.2).

---

## 3. Active cron stack (session-only — die when Claude session ends)

| Loop | Cadence | Cron expr | Job ID (this session) | Purpose |
|---|---|---|---|---|
| Watcher | 2s | Python loop | PID lives on macOS | Live monitoring, exchange-truth guardrail, MFE/MAE tracking |
| Auto SL/TP + Giveback | every 5 min | `4,9,14,19,24,34,39,44,49,54 * * * *` | `502af15c` | Trail SL, fix R:R<2.0 TPs, giveback exits |
| Trade cycle | every 8 min | `5,13,21,29,37,45,53 * * * *` | `125d19c0` | Fills slots when free; confidence-gated leverage |
| Discovery | every 10 min | `2,12,22,32,42,52 * * * *` | `3914a631` | News + Binance Discover/News + 529-symbol scan → watchlist |
| Loss research | every 10 min | `6,16,26,36,46,56 * * * *` | `6bec57ea` | Research + auto-decide on losers ≤ -0.3R |

**Restart cron expressions** when a new session starts (use the CronCreate tool to recreate). The job IDs change per session.

**Watcher restart command:**
```bash
set -a && source .env && set +a && nohup python3 -u -m scripts.run_watch_positions --loop --interval 2 --verbose > /tmp/watcher.log 2>&1 &
```

---

## 4. Bug fixes applied this session (ERROR log in memory/execution-errors.md)

| ID | What | Status |
|---|---|---|
| ERROR-20260511-4 | Watcher's local-trailing logic closed live positions on local-price comparison while exchange position remained open. **FIXED** via exit_simulator no-op of STOP_HIT/FULL_TP/PARTIAL_TP/INVALIDATION_EXIT in live mode + opt-in trailing via EXIT_TRAILING_STOP_ENABLED + exchange-truth-first guardrail. | ✅ Fixed |
| ERROR-20260511-5 | execution_router fired entries without atomically placing SL+TP brackets; live_execution.place_algo_stop_market used legacy /fapi/v1/order schema (Binance migrated to /fapi/v1/algoOrder on 2025-12-09, error -1102). **FIXED** by migrating to new schema (algoType=CONDITIONAL, triggerPrice, clientAlgoId) + atomic bracket placement in execution_router with reduce-only close + safety pause on failure. | ✅ Fixed |
| ERROR-20260511-6 | Watcher's `store.save_all` rewrote the entire open-positions.json file every tick, clobbering concurrent writers (PnL monitor, orchestrator, manual reconciliation). **FIXED** via fcntl.flock + `apply_watcher_updates` whitelist that only mutates allowed fields (max_favorable_pnl, max_adverse_pnl, unrealized_pnl, updated_at, notes). Forward-compat `from_jsonable` filter also added (was silently dropping positions with new fields). | ✅ Fixed |

**Outstanding (NOT YET FIXED):**
- Strategy engine doesn't enforce R:R ≥ 2.0 at proposal-gate level (firing engine may pick R:R 1.43 trades; orchestrator catches them post-hoc and the auto-adjust monitor swaps TPs to TP2-level). Cost: ~3 min cycle time, minor.

---

## 5. Code files modified this session

```
scripts/positions_store.py     — added algo_order_ids field, fcntl lock, apply_watcher_updates whitelist, forward-compat from_jsonable
scripts/watcher.py             — exchange-truth guardrail, removed save_all clobber, opt-in trailing via EXIT_TRAILING_STOP_ENABLED
scripts/exit_simulator.py      — live-mode no-op for STOP_HIT/FULL_TP/PARTIAL_TP/INVALIDATION_EXIT
scripts/live_execution.py      — migrated place_algo_stop_market + place_algo_take_profit_market + cancel_algo_order to new algoOrder schema
scripts/execution_router.py    — atomic bracket placement post-fill + reduce-only-close + safety-pause on failure
scripts/run_full_auto_cycle.py — wires safety into router, propagates algo_order_ids to Position
scripts/run_live_cycle.py      — same as full_auto for SEMI_AUTO mode
scripts/run_watch_positions.py — added --enable-trailing flag, --no-exchange-guardrail, pre-fetches exchange snapshot
config/env.example             — documented EXIT_TRAILING_STOP_ENABLED=false default
tests/test_live_execution.py   — algoOrder schema regression tests
tests/test_execution_router.py — bracket atomicity + naked-rescue tests
tests/test_positions_store.py  — 8 no-clobber race tests
```

**Test status:** **213 passing, 5 skipped** (was 158 at session start). Zero regressions.

---

## 6. Active positions (as of last sync)

Read live state via `set -a && source .env && set +a && python3 -m scripts.binance_position_sync`. As of 2026-05-11T11:03Z the agency held 5 open positions: BUSDT LONG, LABUSDT SHORT, SAGAUSDT LONG, FOLKSUSDT LONG, NAORISUSDT SHORT.

**Always check data/open-positions.json for the source of truth (file-locked) and reconcile with Binance via the sync script.** Both must agree; mismatches block new trades.

---

## 7. Where to find things

| Need | Path |
|---|---|
| Locked policy + agency philosophy | `CLAUDE.md` |
| Live positions (file-locked) | `data/open-positions.json` |
| Watchlist (discovery output) | `data/watchlist.json` |
| PnL snapshots (history) | `data/pnl-snapshots.jsonl` |
| Loss research log | `data/loss-research-log.jsonl` |
| Trade journal | `memory/trade-journal.md` |
| Rejected trades | `memory/rejected-trades.md` |
| Error log + resolutions | `memory/execution-errors.md` |
| Safety events | `memory/safety-events.md` |
| Discovery log | `memory/discovery-log.md` |
| Mode state | `data/mode-state.json` |
| Risk/safety state | `data/risk-state.json` + `data/safety_state.json` |
| API keys | `.env` (BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET=false → LIVE MAINNET) |

---

## 8. New-session boot sequence

If you're a fresh Claude session inheriting this agency:

1. **Read this file.** Don't re-explore from scratch.
2. **Read** `CLAUDE.md` for unchanged trading philosophy.
3. **Run sync:** `set -a && source .env && set +a && python3 -m scripts.binance_position_sync`. Verify `sync_status: success`.
4. **Check watcher:** `ps aux | grep run_watch_positions | grep -v grep`. If not running, restart with the command above.
5. **Recreate crons** using the cron expressions in Section 3. Job IDs will be new.
6. **Read** `memory/execution-errors.md` last 200 lines if you need to know about known bugs/fixes.
7. **Ask user** for any policy changes before firing live trades.

---

## 9. Things the user explicitly cares about

- **Profits > losses.** Be selective. NO TRADE is preferred over a bad trade.
- **Watcher should be live 2s polling.**
- **Discovery should pull from Binance Discover + Binance News + Square + CMC + CoinDesk + The Block + X/Twitter** — not just internal screener.
- **Continuously fill all 5 slots** when quality permits.
- **Active loss management** — research losers, decide hold/exit per-token via token-research-agent.
- **Give-back protection** on winners — don't let a +1.5 USDT gain become a +0.30 USDT scratch.
- **Leverage = confidence-gated.** Only 5x when confidence ≥ 0.85.
- **Always update this file and CLAUDE.md** when policy or system changes.

---

## 10. Recent realized PnL (this session)

| Trade | Result |
|---|---|
| SUIUSDT SHORT (manual iOS close 05-11 01:53Z) | −0.042 USDT |
| DEEPUSDT SHORT (manual iOS close 05-11 01:53Z) | +0.256 USDT |
| **Session realized total (closed trades only)** | **+0.214 USDT net of fees** |

5 active positions held this hour — see live sync for current uPnL.

---

_Last updated: 2026-05-11T11:08Z (after ERROR-20260511-6 fix + giveback-protection rule + leverage gating)._
