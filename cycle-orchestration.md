# Cycle Orchestration — what happens when you run the agency

This is the runtime flow. When you type `/start-trading-workflow` (or run `python -m scripts.run_paper_cycle`), this is the exact sequence of agents that wake up, in order, with what each one reads, decides, and writes.

The agency runs **three independent loops**:

1. **Trade cycle** — scan → research → propose → risk → execute → store position. Triggered by you (slash command or cron).
2. **Watcher loop** — manages already-open positions. Runs continuously (or on a timer).
3. **Approval queue worker** — fires queued semi-auto trades the user has approved. Runs on the next live cycle.

Plus two background tracks that aren't loops but fire on events:

4. **Safety state** — updated whenever a trade closes (records PnL, auto-pauses on breach).
5. **Learning** — aggregates the journal at end-of-day.

---

## TL;DR — the trade cycle in one diagram

```
USER: /start-trading-workflow
        │
        ▼
┌─────────────────────────────┐
│ 1. Agency Orchestrator      │  reads CLAUDE.md + agency/workflow.md
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 2. Mode Manager             │  resolves: paper | live-readiness-only | live-enabled
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 3. Safety / Kill-Switch     │  paused? daily loss breached? consec losses? cooldown?
└─────────────┬───────────────┘
              │ (if blocked → exit)
              ▼
┌─────────────────────────────┐
│ 4. Health Check             │  API reachable? clock skew? data fresh?
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 5. Permission Preflight     │  (live mode only) — withdrawal perm? trading perm?
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 6. Binance Sync             │  wallet, positions, manual-position detection
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 7. Position Manager Reconcile  internal vs exchange — pause on mismatch
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 8. Market Intelligence      │  BTC + ETH bias, regime, no-trade conditions
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ 9. Token Screener           │  scan all USDT-M perps, hard filters, rank top N
└─────────────┬───────────────┘
              │
              ▼
   ┌──────────┴────────────┬──────────────────┬─────────────────┐
   │                       │                  │                 │
   ▼ for each top candidate (parallel-able)                      │
┌─────────────────────────────┐                                  │
│ 10. Token Research          │  4h/1h/15m/5m candles +          │
│     (per symbol)            │  indicators + liquidity + funding│
└─────────────┬───────────────┘                                  │
              │                                                  │
              ▼                                                  │
┌─────────────────────────────┐                                  │
│ 11. Strategy Scoring        │  9 strategies scored, best chosen│
│     (per symbol)            │                                  │
└─────────────┬───────────────┘                                  │
              │                                                  │
              ▼                                                  │
┌─────────────────────────────┐                                  │
│ 12. Trade Decision          │  best setup or no-trade          │
└─────────────┬───────────────┘                                  │
              │ (if no-trade → next candidate)                   │
              ▼                                                  │
┌─────────────────────────────┐                                  │
│ 13. Pre-trade Limits Check  │  paused? daily loss? consec?     │
│                             │  max open? duplicate? per cycle? │
└─────────────┬───────────────┘                                  │
              │ (skip if soft cap, abort if hard cap)            │
              ▼                                                  │
┌─────────────────────────────┐                                  │
│ 14. Risk Manager            │  approve | reject | reduce_size  │
│                             │  | lower_leverage | wait         │
└─────────────┬───────────────┘                                  │
              │ (if not approved → journal rejection)            │
              ▼                                                  │
┌─────────────────────────────┐                                  │
│ 15. Position Sizing         │  qty, leverage, margin, fees,    │
│                             │  Binance filters, MIN_NOTIONAL   │
└─────────────┬───────────────┘                                  │
              │                                                  │
              ▼                                                  │
┌─────────────────────────────┐                                  │
│ 16. Approval Policy         │  notional ≤ $50? first trade?    │
│                             │  daily loss ≥ 75%?               │
└─────────────┬───────────────┘                                  │
              │                                                  │
              ▼                                                  │
┌─────────────────────────────┐                                  │
│ 17. Execution Router        │  → paper / live-auto / queue     │
└─────────────┬───────────────┘                                  │
              │                                                  │
        ┌─────┴─────┬──────────────┐                             │
        ▼           ▼              ▼                             │
   PAPER FILL   LIVE ORDER     QUEUE FOR APPROVAL                │
   simulated    real signed    pending-approvals.json            │
   from depth   POST /order                                      │
        │           │              │                             │
        └─────┬─────┴──────────────┘                             │
              ▼                                                  │
┌─────────────────────────────┐                                  │
│ 18. Position Manager        │  persist to data/open-positions  │
└─────────────┬───────────────┘                                  │
              │                                                  │
              ▼                                                  │
┌─────────────────────────────┐                                  │
│ 19. Telegram Notifier       │  alert with entry-filled template│
└─────────────┬───────────────┘                                  │
              │                                                  │
              └──────────────────────────────► next candidate ───┘
                                                       │
                                                       ▼
                                          (loop until top N done)
                                                       │
                                                       ▼
                                  ┌─────────────────────────────┐
                                  │ 20. User Report             │
                                  │     cycle summary JSON       │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                          Cycle complete.
                                          → Watcher takes over.
```

---

## The trade cycle — step-by-step

Every step lists:
- **Agent** — the conceptual specialist
- **Code** — the actual Python module(s) doing the work
- **Reads** — what files / state / APIs it consumes
- **Writes** — what it changes
- **Failure** — what happens if it fails

### Step 1: Orchestrator

- **Agent**: `agency-orchestrator` (`agents/agency-orchestrator/agent.md`)
- **Code**: `scripts/run_paper_cycle.py::main` / `scripts/run_live_cycle.py::main` / `scripts/run_full_auto_cycle.py::main` / `scripts/trade_workflow_runner.py::main`
- **Reads**: `CLAUDE.md`, `agency/workflow.md`, `agency/safety-rules.md`, `agency/risk-rules.md`, CLI args
- **Writes**: nothing yet — just sets up the report dict and chooses sub-CLIs.
- **Failure**: refuses to start if `--i-understand-this-is-real-money` (live) or `--i-understand-this-fires-trades-without-asking` (full-auto) is missing.

### Step 2: Mode Manager

- **Agent**: implicit (no `.md` agent file — it's a low-level resolver)
- **Code**: `scripts/mode_manager.py::resolve_mode`
- **Reads**: `MODE`, `ALLOW_LIVE_EXECUTION`, `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER`, `TELEGRAM_BOT_TOKEN` (presence only) from `scripts/env_loader.py`
- **Writes**: `data/mode-state.json`
- **Output**: `effective_mode ∈ {paper, live-readiness-only, live-enabled}`
- **Failure**: any blocker → effective_mode falls back to `live-readiness-only` (or `paper`).

### Step 3: Safety / Kill-Switch

- **Agent**: `safety-kill-switch-agent`
- **Code**: `scripts/safety_state.py::SafetyStateManager::check_can_trade` + `perform_daily_rollover_if_needed`
- **Reads**: `data/risk-state.json`, `data/system-health.json`
- **Decides**:
  - Did UTC midnight pass since last cycle? → archive yesterday, zero counters.
  - Is `trading_paused=true`? → check `paused_until_iso`. If cooldown elapsed, auto-resume.
  - Otherwise pass through.
- **Writes**: `data/risk-state.json`, `data/system-health.json` (mirrored)
- **Failure**: paused → cycle exits with `next_actions: ["safety state blocks trading: ..."]`. Existing positions are still monitored by the watcher.

### Step 4: Health Check

- **Agent**: implicit
- **Code**: `scripts/health_check.py::run_health_check`
- **Reads**: `/fapi/v1/time` (public, no auth), `data/risk-state.json`, `data/system-health.json`
- **Decides**:
  - Can we reach Binance?
  - Is server-time skew < 5s? (matters for signed requests)
  - Are data files readable?
- **Writes**: returns `HealthReport` (orchestrator includes it in cycle output)
- **Failure**: API unreachable → cycle exits cleanly. Does not pause the agency (transient network issues shouldn't trip safety-state).

### Step 5: Permission Preflight (live mode only)

- **Agent**: `binance-sync-agent` (delegates to `Account`)
- **Code**: `scripts/account.py::Account::check_permissions`
- **Reads**: `/fapi/v2/account` (signed) + `/sapi/v1/account/apiRestrictions` (signed)
- **Decides**: trading_enabled? withdrawals_enabled? (anything other than `False` = refuse)
- **Writes**: returns `APIPermissionReport`
- **Failure**: withdrawal perm enabled → cycle aborts, status `halted`. **This is non-negotiable.** If the spot endpoint isn't reachable, withdrawals are treated as UNKNOWN → still refuse.

### Step 6: Binance Sync

- **Agent**: `binance-sync-agent`
- **Code**: `scripts/binance_position_sync.py::sync_binance` → calls `scripts/account.py`
- **Reads**: `/fapi/v2/account`, `/fapi/v2/positionRisk`, `/fapi/v1/openOrders`
- **Writes**: `data/synced-binance-positions.json`, `data/manual-positions.json`
- **Detects**: any open Binance position with no internal `proposal_id` → flagged as manual. New manuals trigger a Telegram alert (`send_manual_position_alert`).
- **Failure**: read error → cycle records warning, may proceed in paper mode but lives blocks new orders.

### Step 7: Position Manager Reconcile

- **Agent**: `position-manager-agent`
- **Code**: `scripts/position_manager.py::reconcile`
- **Reads**: `data/open-positions.json` + the Binance snapshot from step 6
- **Decides**: 5 mismatch categories — `missing_on_exchange`, `missing_locally`, `qty_mismatch`, `side_mismatch`, `status_drift`
- **Writes**: `data/system-health.json` (sets `last_reconciliation_clean=false` on mismatch)
- **Failure**: any mismatch → cycle exits, Safety Agent paused with `pause_carry_over_rollover=true` (survives daily UTC reset until manually resolved).

### Step 8: Market Intelligence

- **Agent**: `market-intelligence-agent`
- **Code**: lightweight inline check in the cycle CLI: fetches `BTCUSDT 1h × 12` and reports last 1h change.
- **Reads**: `/fapi/v1/klines?symbol=BTCUSDT&interval=1h&limit=12` (public)
- **Writes**: `report["market_context"]`
- **Decides**: if BTC moved ≥ 2% in the last 1h → adds a warning ("small caps will be jumpy"). Doesn't pause.
- **Future**: full agent that classifies regime (`bullish/bearish/mixed/volatile/dangerous/no_trade`).

### Step 9: Token Screener

- **Agent**: `token-screener-agent`
- **Code**: `scripts/token_screener.py::run_screener`
- **Reads**: `/fapi/v1/exchangeInfo` (1 call, weight 1) + `/fapi/v1/ticker/24hr` (1 call, weight 40, returns ALL symbols) + `/fapi/v1/premiumIndex` (1 call, weight 10, all symbols' funding)
- **Filters**:
  - Decimal-priced only
  - 24h quote volume ≥ `--min-quote-volume` (default 5M USDT)
  - Spread ≤ 20 bps
  - 24h move within `min_abs..max_abs` band (default 1.5–30%)
  - Funding rate within ±0.5% per 8h
  - Not on user avoid-list
  - Not already an open position
- **Output**: `ScreeningResult(candidates, rejected, universe_size)` — top N candidates ranked by composite score
- **Writes**: returns to orchestrator

### Step 10: Token Research (per candidate)

- **Agent**: `token-research-agent`
- **Code**: `scripts/token_research.py::research_token`
- **Reads** (per symbol — ~11 weight total):
  - `/fapi/v1/klines` × 4 timeframes (4h × 200, 1h × 200, 15m × 200, 5m × 100)
  - `/fapi/v1/depth?limit=50`
  - `/fapi/v1/premiumIndex`
  - `/fapi/v1/openInterest`
- **Computes** (`scripts/indicators.py`): EMA-9/21, RSI-14, ATR, realized vol, swing pivots, S/R clustering
- **Output**: `TokenResearchReport` — multi-timeframe summary + structure flags + liquidity profile + no-trade reasons

### Step 11: Strategy Scoring (per researched token)

- **Agent**: `strategy-agent`
- **Code**: `scripts/strategy_scoring.py::rank_strategies`
- **Reads**: `TokenResearchReport`
- **Scores**: 9 strategies — `long_breakout`, `short_breakdown`, `pullback_long`, `pullback_short`, `momentum_continuation`, `failed_breakout_short`, `short_after_pump`, `reversal_scalp`, `range_trade`
- **Output**: `StrategyRanking(scores, best)` — `best` is the highest-confidence ≥ `MIN_CONFIDENCE` (0.6) and not vetoed by no-trade reasons in the research report
- **Failure**: no strategy meets confidence → `best=None`, journal a rejection, move to next candidate.

### Step 12: Trade Decision

- **Agent**: `trade-decision-agent`
- **Code**: implicit — the cycle takes `ranking.best` if present, otherwise no-trade.
- **Output**: a Trade Proposal (matches the schema in `CLAUDE.md`)

### Step 13: Pre-trade Limits Check

- **Agent**: `safety-kill-switch-agent` (delegate)
- **Code**: `scripts/limits.py::check_proposal`
- **Reads**: `SafetyState`, current open positions, `fired_this_cycle` counter
- **Checks**:
  - `paused` (hard cap → abort cycle)
  - `daily_loss_limit` (hard → abort cycle)
  - `consecutive_loss_limit` (hard → abort cycle)
  - `max_open_positions` (soft → skip this proposal, try next)
  - `no_duplicate_symbol` (soft → skip this proposal)
  - `per_cycle_trade_cap` (hard → abort cycle)

### Step 14: Risk Manager

- **Agent**: `risk-manager-agent`
- **Code**: `scripts/risk_engine.py::evaluate_proposal`
- **Reads**: proposal, `SymbolSpec` (Binance filters), `RiskConfig`
- **Computes**:
  - `size_from_risk` — qty, margin, fees, with MIN_NOTIONAL bump-up + max-margin cap
  - `estimate_liquidation_isolated` — distance, is-safe (≥ 30% default)
  - `estimate_profit` — gross, fees, net, R:R, fee-to-profit ratio, is-meaningful (≥ 3% of margin)
- **Output**: `RiskApproval` — `approved | rejected | reduce_size | lower_leverage | wait`
- **Failure modes**: anything other than `approved` → journal a rejection (`memory/rejected-trades.md`), move to next candidate.

### Step 15: Position Sizing

- **Agent**: `position-sizing-agent`
- **Code**: same `risk_engine` call — sizing is computed during evaluation.
- **Output**: an Execution Plan (qty, leverage, margin, stop, TPs)

### Step 16: Approval Policy (semi-auto live only)

- **Agent**: implicit (rule engine)
- **Code**: `scripts/approval_policy.py::evaluate`
- **Reads**: notional, leverage, daily PnL, `is_first_live_trade_of_session`, `ApprovalPolicy(notional_threshold_usdt=50)`
- **Decides**:
  - Notional > $50 → require approval
  - First live trade of session → always require approval
  - Daily loss ≥ 75% of limit → always require approval
  - High leverage (> 5x) → flag in journal, doesn't by itself queue
- **In paper / full-auto**: returns `requires_user_approval=False` always.

### Step 17: Execution Router

- **Agent**: `execution-agent`
- **Code**: `scripts/execution_router.py::ExecutionRouter::route`
- **Branches**:
  - `mode=PAPER_TRADING` → `paper_execution.simulate_market_fill` (depth-aware fill from `/fapi/v1/depth`)
  - `mode=SEMI_AUTO_LIVE` + `requires_user_approval=False` → `live_execution.place_market_entry` (real order)
  - `mode=SEMI_AUTO_LIVE` + `requires_user_approval=True` → `pending_approvals.upsert` (queues, exits cleanly)
  - `mode=FULL_AUTO_LIVE` → `live_execution.place_market_entry` (real order, no approval)
- **Output**: `ExecutionOutcome` with `status ∈ {filled, paper_filled, queued_for_approval, rejected}`

### Step 18: Position Manager (persist)

- **Agent**: `position-manager-agent`
- **Code**: `scripts/positions_store.py::PositionsStore::upsert`
- **Reads**: existing `data/open-positions.json`
- **Writes**: atomically (temp file + rename) — appends or updates the position
- **The position now belongs to the watcher loop.**

### Step 19: Telegram Notifier

- **Agent**: `telegram-control-agent`
- **Code**: `scripts/telegram_notifier.py::send_entry_filled` (or `send_trade_proposal` / `send_risk_rejected` etc. depending on outcome)
- **Reads**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` from env
- **Writes**: `data/telegram-events.jsonl`
- **Failure**: Telegram down → logs and continues. Does not block the cycle.

### Step 20: User Report

- **Agent**: `user-report-agent`
- **Code**: end of `run_*_cycle.py` — emits the cycle summary JSON to stdout + writes `data/agency-state.json`.
- **Output**: structured report with `summary`, `routed_outcomes`, `opened_positions`, `warnings`, `next_actions`.

---

## The watcher loop — what runs while positions are open

Started by you (or cron) via `python -m scripts.run_watch_positions --loop --interval 60`.

```
TICK (every interval seconds)
        │
        ▼
┌─────────────────────────────────────────────┐
│ Watcher Agent                               │
│   load data/open-positions.json             │
└──────────────────┬──────────────────────────┘
                   │
                   ▼ for each open position
┌─────────────────────────────────────────────┐
│ 1. Fetch /fapi/v1/klines (1m × 30)          │
│    Compute ATR over the lookback window     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 2. Mark-to-market                            │
│    update unrealized_pnl, MFE, MAE          │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 3. Profit Protection Advisor                 │
│    scripts/profit_protection.py::advise     │
│    suggests partial / breakeven / trail /    │
│    exit_now                                  │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 4. Exit Simulator                            │
│    decide_from_candle(pos, candle, atr)     │
│    → hold | partial_tp | full_tp |          │
│      stop_hit | trail_stop |                │
│      move_stop_breakeven |                  │
│      invalidation_exit | emergency_exit     │
└──────────────────┬──────────────────────────┘
                   │
            ┌──────┴──────┐
            │             │
            ▼             ▼
        HOLD           non-hold decision
        update mark    │
        and continue   ▼
                ┌─────────────────────────────┐
                │ 5. Apply Decision           │
                │   apply_decision(pos, dec)  │
                │   - mutates position        │
                │   - subtracts fees          │
                │   - sets status=closed if   │
                │     terminal                │
                └─────────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │ 6. Persist position         │
                │    PositionsStore.save_all  │
                └─────────────┬───────────────┘
                              │
                              ▼ (only if terminal)
                ┌─────────────────────────────┐
                │ 7. Journal closed trade     │
                │   append_paper_trade        │
                │   → memory/trade-journal.md │
                └─────────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │ 8. SafetyState.record_trade_close
                │   - update daily_pnl_usdt    │
                │   - increment consec_losses  │
                │     (or wins, resetting losses)│
                │   - AUTO-PAUSE on breach     │
                └─────────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │ 9. Telegram trade-closed    │
                │    summary                  │
                └─────────────────────────────┘
```

**Key safety property of the watcher**: when it auto-pauses the agency (step 8 breach), the next trade cycle's step 3 sees the pause and exits before doing any work. New trades stop immediately. Existing positions remain monitored.

---

## The approval queue worker

When `run_live_cycle` starts (semi-auto), step 0.5 (before scanning) is:

```
ExecutionRouter.execute_approved_queue(spec_lookup)
        │
        ▼
For each pending_approval where status=='approved':
        │
        ▼
   Fire live order (same code path as auto-fired live trade)
        │
        ▼
   On success: status='executed', record order_id + avg_price
   On failure: status='rejected', record error message
```

Stale approvals (past `deadline_at`) are auto-`expired` at the start of the worker pass.

You set `status='approved'` via `python -m scripts.run_approvals --approve APRV-...` or `--inline`.

---

## Background tracks

### Safety state updates

Whenever a trade closes (watcher step 8), `SafetyStateManager.record_trade_close(net_pnl)`:

1. Performs daily rollover if needed (UTC date changed since `daily_period_start`).
2. Adds `net_pnl` to `daily_pnl_usdt`.
3. If `net_pnl > 0`: increment consecutive_wins, zero consecutive_losses.
4. If `net_pnl < 0`: increment consecutive_losses, zero consecutive_wins.
5. Compute breach:
   - `daily_pnl_usdt ≤ -daily_loss_limit_usdt` → pause (no cooldown — until UTC midnight or `--resume`).
   - `consecutive_losses ≥ consecutive_loss_limit` → pause with 60-min cooldown.
6. Mirror to `data/system-health.json`.

### Learning aggregation

Triggered manually via `python -m scripts.run_learning_report --persist` (or end-of-day `/daily-report`).

```
Learning Agent
        │
        ▼
   Parse memory/trade-journal.md (every TRADE-* block)
   Parse memory/rejected-trades.md (every REJECTED-* block)
        │
        ▼
   Aggregate per strategy / per symbol / per regime / per exit reason
        │
        ▼
   Apply statistical floor (default n ≥ 20)
        │
        ▼
   For each strategy passing the floor:
     - win rate ≥ 55% AND positive expectancy → "consider raising priority"
     - win rate ≤ 35% OR negative expectancy at n ≥ 30 → "consider raising MIN_CONFIDENCE / pausing"
        │
        ▼
   Append insights to memory/learning-insights.md (with insight_id dedupe)
   requires_user_approval=true on every actionable insight
   safety_impact=none|low|medium|high
```

The Learning Agent **never auto-raises risk caps**. Every recommendation needs your explicit nod.

---

## Where each step writes

| Step | Writes |
|---|---|
| 2 (mode) | `data/mode-state.json` |
| 3 (safety) | `data/risk-state.json`, `data/system-health.json` |
| 6 (sync) | `data/synced-binance-positions.json`, `data/manual-positions.json` |
| 7 (reconcile) | `data/system-health.json` |
| 14 (risk) | `memory/rejected-trades.md` (on reject) |
| 16 (approval) | `data/pending-approvals.json` (on queue) |
| 17 (execution) | nothing yet |
| 18 (position) | `data/open-positions.json` |
| 19 (telegram) | `data/telegram-events.jsonl` |
| 20 (report) | `data/agency-state.json` (last cycle summary) |
| Watcher 6 | `data/open-positions.json` |
| Watcher 7 | `memory/trade-journal.md` |
| Watcher 8 | `data/risk-state.json`, `data/system-health.json` |
| Watcher 9 | `data/telegram-events.jsonl` |
| Learning | `memory/learning-insights.md` |

Every write goes through atomic-write (temp file + rename) so a crash mid-write never corrupts state.

---

## What can fail and what happens next

| Failure | Cycle behaviour | Next action |
|---|---|---|
| `MODE` invalid / missing | Effective mode = `paper` | Cycle runs in paper |
| Binance unreachable | Cycle exits, no orders | Retry next cycle (transient) |
| Permission preflight: withdrawal enabled | Cycle aborts | User must disable withdrawal on key |
| Reconcile mismatch | Cycle aborts, safety pause with carry-over | User runs `/sync-binance` + investigates |
| Daily loss breach | Cycle aborts, safety pause until UTC midnight | Wait or `--resume` after review |
| Consecutive loss breach | Cycle aborts, 60-min cooldown auto-resume | Wait OR `--resume` early |
| Risk Manager rejects | Journal rejection, try next candidate | None — system worked correctly |
| Order book too thin | Reject with `thin order book` reason | Try a different symbol |
| Live order rejected by Binance | Outcome = `rejected`, journal | Investigate Binance error code |
| Telegram down | Logs, cycle continues | Cycle finishes; just no alerts |
| Watcher candle fetch fails (one symbol) | Warning recorded, other positions still managed | Next watcher tick retries |
| Position closed while watcher off | Rediscovered as `missing_locally` next sync | Reconciliation alerts user |

The general principle: **paper-side failures journal and continue. Live-side failures pause first, alert second, never silently retry an order.**

---

## Where to look when debugging

| Symptom | First file to read |
|---|---|
| "Cycle says it's halted but I don't know why" | `data/system-health.json` → `paused_reason` |
| "Why didn't this trade fire?" | `memory/rejected-trades.md` |
| "Did the order actually go through?" | `data/agency-state.json::last_summary`, then Binance UI |
| "What's my daily PnL right now?" | `data/risk-state.json::daily_pnl_usdt` |
| "Why did Telegram say it's a manual position?" | `data/manual-positions.json` |
| "Did the watcher run?" | `memory/trade-journal.md` for closures, `data/telegram-events.jsonl` for sends |
| "What insight did the learning agent surface?" | `memory/learning-insights.md` |
| "Was Binance reachable when this happened?" | Cycle log output (look for "WARNING transient...") |

---

## Companion docs

- `wiki.md` — full operating reference (env vars, all CLIs, file layout, safety rails)
- `claude-code-routine.md` — daily slash-command-driven workflow
- `github-setup.md` — optional GitHub setup
- `agency/workflow.md` — the canonical 15-step agency workflow
- `CLAUDE.md` — the system prompt that teaches Claude this orchestration
