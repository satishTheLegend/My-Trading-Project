# scripts/

Phase 2 + 3 + 4 implementation. Standard library only — no pip install
required to run a paper cycle, watch positions, generate a learning report,
or place live testnet orders.

## Modules

| File | What it does | Phase |
|---|---|---|
| `binance_client.py` | Public USDT-M Futures HTTP client. Weight-aware rate limiting, exponential backoff, no auth. | 2 |
| `symbol_filters.py` | Parse `exchangeInfo`, validate orders against `PRICE_FILTER`/`LOT_SIZE`/`MIN_NOTIONAL`/`MARKET_LOT_SIZE`. Decimal-correct rounding. | 2 |
| `market_data.py` | Typed wrappers: candles, 24h ticker, depth, mark price, funding rate, open interest. | 2 |
| `indicators.py` | EMA, SMA, ATR, RSI, VWAP, Bollinger, swing pivots, S/R clustering, realised vol. | 2 |
| `token_screener.py` | Scan all USDT-M perps, apply hard filters, rank candidates. | 2 |
| `token_research.py` | Multi-timeframe deep research per symbol → `TokenResearchReport`. | 2 |
| `strategy_scoring.py` | 9 strategy scorers → `StrategyRanking`. | 2 |
| `risk_engine.py` | Position sizing (with MIN_NOTIONAL bump-up + max-margin cap), isolated-margin liquidation, fee-aware profit, full proposal evaluation. | 2 |
| `journal_writer.py` | Append-only writer for `memory/trade-journal.md` and friends. | 2 |
| `health_check.py` | Safety Agent's API/data probe. | 2 |
| `paper_execution.py` | Depth-aware market & limit fill simulator → `PaperFill`. | 3 |
| `positions_store.py` | Atomic-write store for `data/open-positions.json` → typed `Position`. | 3 |
| `exit_simulator.py` | Pure exit-decision engine. Conservative tie-break: stop wins ties with TP. | 3 |
| `watcher.py` | Single watcher tick over all open positions. | 3 |
| `backtester.py` | Walk-forward historical sim. Aggregates per-strategy stats. | 3 |
| `learning.py` | Journal aggregator → `LearningReport` with statistical-floor-gated insights. Never auto-raises risk. | 3 |
| `binance_signed_client.py` | **HMAC-SHA256 signed client.** Defaults to testnet; mainnet requires `BINANCE_LIVE=true`. Signed gate must be opened by Safety Agent. | 4 |
| `account.py` | Typed account snapshot + permission preflight. **Refuses signed requests if API key has withdrawal permission.** | 4 |
| `live_execution.py` | Sibling of `paper_execution`. Always reduce-only on exits. Idempotent margin/leverage handling. | 4 |
| `position_manager.py` | Reconcile `data/open-positions.json` vs `/fapi/v2/positionRisk`. Surfaces drift to Safety Agent. | 4 |
| `emergency_close.py` | Close every open Binance position with reduce-only market orders, verify residual is zero, log to `memory/safety-events.md`. | 4 |
| `approval_policy.py` | Pure rules: when does a trade need human approval? Default threshold: **notional > $50**. Plus first-trade-of-session and daily-loss-≥75% defensive overrides. | 5 |
| `pending_approvals.py` | Atomic-write store for `data/pending-approvals.json`. States: `pending → approved → executed` (or `rejected` / `expired` / `cancelled`). | 5 |
| `execution_router.py` | Single chokepoint between orchestrator and execution. Decides paper vs live vs queue. The only module besides explicit CLIs that imports `live_execution`. | 5 |
| `safety_state.py` | Centralized SafetyStateManager: daily PnL + consecutive losses + auto-pause + UTC daily rollover + manual pause/resume. Owns mutation of `data/risk-state.json` + `data/system-health.json`. | 6 |
| `limits.py` | Pure pre-trade limit checker: paused / daily_loss / consecutive_loss / max_open_positions / no_duplicate_symbol / per_cycle_trade_cap. | 6 |
| `run_paper_cycle.py` | End-to-end paper CLI. | 2 + 3 |
| `run_watch_positions.py` | CLI: single watcher tick (or `--loop --interval 60`). | 3 |
| `run_backtest.py` | CLI: backtest a symbol over N bars. | 3 |
| `run_learning_report.py` | CLI: aggregate journal → JSON report (`--persist` to write `memory/learning-insights.md`). | 3 |
| `run_emergency_close.py` | CLI: close every open Binance position. **Requires `--i-understand`.** | 4 |
| `run_reconcile.py` | CLI: one reconciliation tick (or `--loop`). | 4 |
| `run_live_cycle.py` | **SEMI_AUTO_LIVE** entrypoint. Same scan/research/risk pipeline as `run_paper_cycle`, but routes through `execution_router`. Auto-fires below `--approval-threshold` (default $50); queues larger trades. | 5 |
| `run_approvals.py` | Manage the approval queue: `--list`, `--inline`, `--approve <id>`, `--reject <id> --reason ...`, `--expire`, `--prune`. | 5 |
| `run_full_auto_cycle.py` | **FULL_AUTO_LIVE** entrypoint. Mandatory `--i-understand-this-fires-trades-without-asking`. Strict caps enforced between proposals. | 6 |
| `run_safety_reset.py` | Manual SafetyState ops: `--status`, `--resume`, `--reset-daily`, `--pause --reason "..." --until-minutes N`. Every action writes a Safety Event. | 6 |

## Quick start

### Paper trading (no money at risk)

```bash
python -m scripts.run_paper_cycle --top 3 --save
python -m scripts.run_watch_positions --loop --interval 60
python -m scripts.run_backtest --symbol DOGEUSDT --interval 1h --bars 500
python -m scripts.run_learning_report --persist
```

### Live testnet (Binance Futures testnet — no real money)

```bash
# 1) Get a testnet API key from https://testnet.binancefuture.com
# 2) Set it (NEVER commit, NEVER paste in chat):
export BINANCE_API_KEY="<paste-here>"
export BINANCE_API_SECRET="<paste-here>"

# 3) Test the connection — will refuse if your key has withdrawal permission:
python -m scripts.run_reconcile --no-permission-check    # use only on testnet

# 4) When the day comes that you actually want to put real money on the line:
export BINANCE_LIVE=true        # default is testnet; this opts in to mainnet
python -m scripts.run_reconcile

# Emergency: close every open Binance position right now:
python -m scripts.run_emergency_close --i-understand --reason "BTC dumped 5%"
```

### Semi-auto live (Phase 5 — your default once you trust the agency)

```bash
# Same env vars as testnet/live.
export BINANCE_API_KEY="..."
export BINANCE_API_SECRET="..."

# Run a SEMI_AUTO_LIVE cycle. Trades ≤ $50 notional auto-fire;
# trades > $50 land in data/pending-approvals.json and exit cleanly.
python -m scripts.run_live_cycle --i-understand-this-is-real-money --top 3

# (Optional) tighten / loosen the threshold per cycle:
python -m scripts.run_live_cycle --i-understand-this-is-real-money --top 3 \
    --approval-threshold 25

# Review queued trades:
python -m scripts.run_approvals --list
python -m scripts.run_approvals --inline                # interactive y/N

# Approve / reject specific entries:
python -m scripts.run_approvals --approve APRV-...
python -m scripts.run_approvals --reject  APRV-... --reason "BTC just dumped"

# Next live cycle picks up approved entries and fires them:
python -m scripts.run_live_cycle --i-understand-this-is-real-money --top 3
```

### Full-auto live (Phase 6 — only after you've watched semi-auto for a while)

```bash
# Same env vars. Defaults to testnet; export BINANCE_LIVE=true for mainnet.
export BINANCE_API_KEY="..."
export BINANCE_API_SECRET="..."

# One full-auto cycle. Every Risk-Manager-approved trade fires automatically.
# Strict caps enforced between proposals; mid-cycle breach stops further trades.
python -m scripts.run_full_auto_cycle \
    --i-understand-this-fires-trades-without-asking \
    --top 3 \
    --daily-loss-limit-usdt 1.5 \
    --consecutive-loss-limit 3 \
    --max-open-positions 2 \
    --per-cycle-trade-cap 5

# Wrap in cron / launchd for cadence (e.g. every 15 min):
*/15 * * * * cd ~/Documents/Claude/Projects/My-Trading-Project && \
    BINANCE_API_KEY=... BINANCE_API_SECRET=... \
    python -m scripts.run_full_auto_cycle \
        --i-understand-this-fires-trades-without-asking --top 3 \
    >> ~/auto.log 2>&1

# Manual safety ops:
python -m scripts.run_safety_reset --status
python -m scripts.run_safety_reset --pause --reason "I'm sleeping" --until-minutes 480
python -m scripts.run_safety_reset --resume --reason "verified market is calm"
python -m scripts.run_safety_reset --reset-daily

# Daily rollover happens automatically at UTC midnight on the first cycle of the new day.
# Soft pauses clear on rollover; hard pauses (carry_over_rollover=True) persist.
```

### Safety rails (the agency enforces these — you can't disable them in code)

- API key + secret read **only** from environment variables.
- `binance_signed_client` defaults to **testnet**; mainnet requires `BINANCE_LIVE=true`.
- Signed requests are **refused** until `Safety Agent → enable_signed_requests()` is called.
- Permission preflight **refuses** to trade if the key has withdrawal permission.
- Exit functions **always** pass `reduceOnly=True`. There's no override switch.
- `run_emergency_close.py` requires `--i-understand` (no accidents from Ctrl-Tab).

## Tests

```bash
# Stdlib-only test runner (no pytest required):
python tools/run_offline_tests.py
# → 110 unit tests + Phase 2 + Phase 3 synthetic pipelines

# Or with pytest installed:
pytest tests/ -v

# Plus opt-in live smoke tests against Binance public API:
BINANCE_LIVE_TESTS=1 pytest tests/test_smoke_live.py -v
```

## Phase 5 next

Wires the live execution layer into `run_paper_cycle.py` behind a
`SEMI_AUTO_LIVE` mode switch. Every approved proposal pauses for explicit
user approval (one prompt per trade) before firing the order. Phase 6 then
unlocks `FULL_AUTO_LIVE` with strict daily-loss/consecutive-loss caps.
