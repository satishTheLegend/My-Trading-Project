# Binance Futures AI Trading Agency — Operating Wiki

The single reference for setting up, running, and operating the agency. Read it once end-to-end before you do anything live.

> **Using Claude Code?** Read `claude-code-routine.md` for the slash-command-driven daily workflow. This file is the underlying reference — env vars, all CLIs, file layout, safety rails. Both docs stay in sync; the routine doc points back here for the details.

## Contents

1. [What this is](#1-what-this-is)
2. [Prerequisites](#2-prerequisites)
3. [First-time setup](#3-first-time-setup)
4. [Environment variables — full reference](#4-environment-variables--full-reference)
5. [The three operating modes](#5-the-three-operating-modes)
6. [Day-one paper workflow](#6-day-one-paper-workflow)
7. [Live testnet workflow](#7-live-testnet-workflow)
8. [Semi-auto live (production)](#8-semi-auto-live-production)
9. [Full-auto live (production)](#9-full-auto-live-production)
10. [Telegram bot setup + commands](#10-telegram-bot-setup--commands)
11. [Every CLI — quick reference](#11-every-cli--quick-reference)
12. [File layout — what writes where](#12-file-layout--what-writes-where)
13. [Safety rails — what cannot be turned off](#13-safety-rails--what-cannot-be-turned-off)
14. [Troubleshooting](#14-troubleshooting)
15. [Tests](#15-tests)
16. [Glossary](#16-glossary)

---

## 1. What this is

A multi-agent Binance USDT-M Futures trading system with three execution modes:

- **Paper** — simulated fills, real market data, no money at risk.
- **Semi-auto live** — real orders, but trades over a notional threshold (default $50) need your explicit approval first.
- **Full-auto live** — real orders, all decisions automatic, hard caps enforced (daily loss, consecutive loss, max open positions, etc.).

Default mode is **paper**. Going live is intentionally an explicit, multi-step process.

The agency is composed of 18 specialised agents (Safety, Risk Manager, Execution, Watcher, Exit, Journal, etc.). Their definitions live in `.claude/agents/` and `agents/<name>/`. Their behaviour is implemented in `scripts/`.

---

## 2. Prerequisites

- **Python 3.10+** (no third-party packages required for core operation — stdlib only).
- A Binance Futures account. For testnet: register at [https://testnet.binancefuture.com](https://testnet.binancefuture.com) and create an API key.
- Optional: a Telegram bot token (talk to [@BotFather](https://t.me/BotFather) on Telegram) and your numeric chat ID (talk to [@userinfobot](https://t.me/userinfobot) to get it).

That's it. No `pip install` needed for paper trading.

---

## 3. First-time setup

```bash
cd ~/Documents/Claude/Projects/My-Trading-Project

# 1. Sanity check — the offline test suite should pass:
python tools/run_offline_tests.py
# → expects "ALL GREEN" with 198 tests passing.

# 2. Copy the env template and fill in what you have:
cp config/env.example .env
$EDITOR .env

# 3. Source it before running any cycle:
set -a; source .env; set +a

# 4. (Optional) verify the agency is in a clean state:
python -m scripts.mode_manager --status
```

Expected output of `mode_manager --status` before you set anything:

```json
{
  "requested_mode": "paper",
  "effective_mode": "paper",
  "live_execution_allowed": false,
  "warnings": [],
  "blockers": []
}
```

---

## 4. Environment variables — full reference

All env vars live in `config/env.example`. Copy that file to `.env` and edit. **Never commit `.env`.**

### Mode

| Variable | Default | Effect |
|---|---|---|
| `MODE` | `paper` | `paper` or `live`. Anything else → `paper`. |
| `ALLOW_LIVE_EXECUTION` | `false` | Must be `true` AND `MODE=live` for any real orders. |

### Binance

| Variable | Default | Effect |
|---|---|---|
| `BINANCE_API_KEY` | *(empty)* | Read from env only. Never put in code/logs. |
| `BINANCE_API_SECRET` | *(empty)* | Same. |
| `BINANCE_TESTNET` | `true` | Default routes to `https://testnet.binancefuture.com`. |
| `BINANCE_REQUIRE_NO_WITHDRAW_PERMISSION` | `true` | If the key has withdrawal permission, all signed calls are refused. |
| `BINANCE_DEFAULT_MARGIN_MODE` | `ISOLATED` | |
| `BINANCE_DEFAULT_LEVERAGE` | `3` | |
| `BINANCE_MAX_LEVERAGE` | `5` | Risk Manager cap. |

### Wallet / risk

| Variable | Default | Effect |
|---|---|---|
| `MIN_WALLET_BALANCE_USDT` | `5` | Below this, no new trades. |
| `MAX_MARGIN_PER_TRADE_PERCENT` | `20` | % of wallet (informational). |
| `MAX_MARGIN_PER_TRADE_USDT` | `2` | Hard cap on margin per trade. |
| `MAX_PLANNED_LOSS_PER_TRADE_MARGIN_PERCENT` | `5` | Stop-loss budget per trade. |
| `DAILY_MAX_LOSS_PERCENT` | `15` | Of wallet — breach pauses trading until UTC midnight or `--resume`. |
| `MAX_CONSECUTIVE_LOSSES` | `3` | Breach pauses with 60-min cooldown. |
| `MAX_OPEN_POSITIONS` | `2` | |

### Telegram

| Variable | Default | Effect |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | *(empty)* | If empty, Telegram is disabled silently — cycles still run. |
| `TELEGRAM_CHAT_ID` | *(empty)* | Primary chat that receives alerts + can send commands. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | *(empty)* | Comma-separated list of additional allowed chats. |
| `TELEGRAM_ENABLE_LONG_POLLING` | `true` | Default. Webhook is opt-in. |
| `TELEGRAM_ENABLE_WEBHOOK` | `false` | |
| `TELEGRAM_WEBHOOK_URL` | *(empty)* | Public HTTPS URL when using webhook mode. |

### Manual position policy

| Variable | Default | Effect |
|---|---|---|
| `ALLOW_MANUAL_POSITION_MANAGEMENT` | `true` | Watcher monitors manual positions. |
| `ALLOW_AUTO_CLOSE_MANUAL_POSITIONS` | `false` | If false, agency only alerts; user closes manually. |

### Confirmation policy

| Variable | Default | Effect |
|---|---|---|
| `REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER` | `false` | If true, no Telegram → no live order. |

### Claude bridge

| Variable | Default | Effect |
|---|---|---|
| `CLAUDE_CONTROL_MODE` | `local` | Reserved for Phase 7 (LLM-powered `/ask`). |
| `CLAUDE_COMMAND_TIMEOUT_SECONDS` | `120` | |

---

## 5. The three operating modes

### Mode resolution

The effective mode is computed by `scripts/mode_manager.py` from `MODE` + `ALLOW_LIVE_EXECUTION` + presence of credentials:

| `MODE` | `ALLOW_LIVE_EXECUTION` | Binance creds | Effective mode |
|---|---|---|---|
| (any other) | (any) | (any) | `paper` |
| `paper` | (any) | (any) | `paper` |
| `live` | `false` | (any) | `live-readiness-only` |
| `live` | `true` | missing | `live-readiness-only` |
| `live` | `true` | present | `live-enabled` |

**`live-readiness-only`** runs the same scan/research/risk pipeline as paper but never sends signed orders — it lets you verify everything is wired correctly without putting money at risk.

### Mode → CLI mapping

| Effective mode | CLI to use | Auto-fires? |
|---|---|---|
| `paper` | `python -m scripts.run_paper_cycle` | n/a (paper) |
| `live-readiness-only` | `python -m scripts.run_paper_cycle` | no |
| `live-enabled` (semi-auto) | `python -m scripts.run_live_cycle` | only if notional ≤ approval threshold |
| `live-enabled` (full-auto) | `python -m scripts.run_full_auto_cycle` | yes, with strict caps |

You can also use the unified dispatcher: `python -m scripts.trade_workflow_runner` — it picks the right cycle based on `mode_manager.resolve_mode()`.

---

## 6. Day-one paper workflow

The standard "I want to use this safely" loop:

```bash
cd ~/Documents/Claude/Projects/My-Trading-Project
set -a; source .env; set +a       # MODE=paper

# 1. Run a paper cycle. The orchestrator scans, researches the top 3
#    candidates, runs the risk engine, and (if approved) opens a tracked
#    paper position.
python -m scripts.run_paper_cycle --top 3 --save

# 2. Watch the open paper positions until they close. Loop every 60s.
python -m scripts.run_watch_positions --loop --interval 60

# 3. After a trading day, generate the learning report.
python -m scripts.run_learning_report --persist

# 4. Backtest a symbol you're curious about (last ~3 weeks of 1h data):
python -m scripts.run_backtest --symbol DOGEUSDT --interval 1h --bars 500
```

**Useful flags on `run_paper_cycle`:**

```bash
--top N                     # research the top N screener candidates (default 3)
--symbol DOGEUSDT           # bypass screener, research a specific symbol
--min-quote-volume 5000000  # tighter screener: require 5M USDT 24h volume
--save                      # persist position + journal entries (skip for dry run)
-v                          # verbose logging
```

`--save` is the difference between "see what would have happened" and "track this position through to close in `data/open-positions.json`". The watcher only manages saved positions.

---

## 7. Live testnet workflow

Use this BEFORE you flip the live switch. Same code path as production, no real money.

```bash
# 1. Get a testnet API key from https://testnet.binancefuture.com
#    (separate from your mainnet account!).

# 2. Set env vars:
export BINANCE_API_KEY="your-testnet-key"
export BINANCE_API_SECRET="your-testnet-secret"
export BINANCE_TESTNET=true        # default, but be explicit
export MODE=live
export ALLOW_LIVE_EXECUTION=true

# 3. Verify mode resolves to live-enabled:
python -m scripts.mode_manager --status

# 4. Probe the connection + permissions WITHOUT placing orders:
python -m scripts.run_reconcile

# Expected behavior:
#   - permission preflight passes (testnet keys never have withdrawal perm)
#   - any positions you opened manually on the testnet UI show up as
#     manual_positions_detected
#   - synced-binance-positions.json gets written

# 5. Optional dry-run of a semi-auto cycle (still hits the testnet, but the
#    $50 threshold means it queues — doesn't actually fire — until you
#    explicitly approve):
python -m scripts.run_live_cycle --i-understand-this-is-real-money --top 3

# 6. Approve a queued trade if you want to see it actually go through:
python -m scripts.run_approvals --inline

# 7. Emergency-close everything on the testnet account when done:
python -m scripts.run_emergency_close --i-understand --reason "testnet cleanup"
```

---

## 8. Semi-auto live (production)

Same as testnet, but with `BINANCE_TESTNET=false`. The approval rule is what makes this safe:

- **Notional ≤ $50** → auto-fires through `live_execution`.
- **Notional > $50** → queues in `data/pending-approvals.json` and you decide.
- **Defensive overrides that always queue** (regardless of notional):
  - First live trade of a process lifetime.
  - Daily loss already consumed ≥ 75% of `DAILY_MAX_LOSS_PERCENT`.

```bash
export BINANCE_TESTNET=false        # mainnet
export MODE=live
export ALLOW_LIVE_EXECUTION=true

# Run a live cycle:
python -m scripts.run_live_cycle --i-understand-this-is-real-money --top 3

# Tighten the threshold per cycle if you want stricter behavior:
python -m scripts.run_live_cycle --i-understand-this-is-real-money --top 3 \
    --approval-threshold 25

# Review queued trades:
python -m scripts.run_approvals --list

# Walk every queued trade interactively (y/n/r/c per entry):
python -m scripts.run_approvals --inline

# Or approve / reject by ID:
python -m scripts.run_approvals --approve APRV-20260510-143000-DOGEUSDT-001
python -m scripts.run_approvals --reject  APRV-... --reason "BTC dumped"

# Next live cycle picks up approved entries and fires them:
python -m scripts.run_live_cycle --i-understand-this-is-real-money --top 3
```

While positions are open, run the watcher in another terminal:

```bash
python -m scripts.run_watch_positions --loop --interval 60
```

---

## 9. Full-auto live (production)

Only do this after you've watched semi-auto for several days and trust the agency on the symbols + market regime you're trading.

```bash
export BINANCE_TESTNET=false
export MODE=live
export ALLOW_LIVE_EXECUTION=true

# One full-auto cycle. Strict caps are enforced between proposals.
python -m scripts.run_full_auto_cycle \
    --i-understand-this-fires-trades-without-asking \
    --top 3 \
    --daily-loss-limit-usdt 1.5 \
    --consecutive-loss-limit 3 \
    --max-open-positions 2 \
    --per-cycle-trade-cap 5

# Wrap in cron / launchd for cadence (every 15 min, log to file):
*/15 * * * * cd ~/Documents/Claude/Projects/My-Trading-Project && \
    BINANCE_API_KEY=... BINANCE_API_SECRET=... \
    BINANCE_LIVE=true MODE=live ALLOW_LIVE_EXECUTION=true \
    python -m scripts.run_full_auto_cycle \
        --i-understand-this-fires-trades-without-asking --top 3 \
    >> ~/auto.log 2>&1
```

What happens automatically:

- Daily UTC midnight rollover zeroes the per-day counters.
- 3 losses in a row → auto-pause with 60-min cooldown.
- Daily loss ≥ limit → pause until midnight or `run_safety_reset --resume`.
- Mid-cycle breach (e.g. a fill that loses big) stops further trades that cycle.
- Max-open-positions / no-duplicate-symbol skip the offending proposal but the cycle continues.

Manual safety ops:

```bash
python -m scripts.run_safety_reset --status
python -m scripts.run_safety_reset --pause --reason "I'm sleeping" --until-minutes 480
python -m scripts.run_safety_reset --resume --reason "verified market is calm"
python -m scripts.run_safety_reset --reset-daily
```

---

## 10. Telegram bot setup + commands

### Setup

```bash
# 1. Create a bot via BotFather. Save the token.
# 2. Get your numeric chat ID via @userinfobot.
# 3. Set env vars:
export TELEGRAM_BOT_TOKEN="123456:ABCDEF..."
export TELEGRAM_CHAT_ID="123456789"
export TELEGRAM_ALLOWED_CHAT_IDS=""        # optional additional chats

# 4. Verify the bot can reach Telegram:
python -m scripts.telegram_bot --get-me

# 5. Register the command menu:
python -m scripts.telegram_bot --register

# 6. Start the long-polling loop (keep this running):
python -m scripts.telegram_bot --poll
```

### Commands

The bot ships 21 commands. Type `/` in your chat to see the menu.

| Command | What it does |
|---|---|
| `/start`, `/help` | Show command list |
| `/status` | Mode + safety + Telegram state |
| `/mode` | Resolved effective mode + blockers |
| `/paper`, `/live` | Reminder how to switch (env-based) |
| `/scan` | Reminder to run the scan from the host |
| `/positions` | Open agency-managed positions |
| `/sync` | Reminder to run binance_position_sync |
| `/summary` | Where to find the latest trade summary |
| `/pause` | Pause trading (delegates to Safety Agent) |
| `/resume` | Resume after a pause |
| `/close SYMBOL` | Request reduce-only close for a symbol |
| `/emergency` | Trigger emergency shutdown |
| `/risk` | Show risk caps |
| `/pnl` | Where to find PnL summary |
| `/journal` | Where journal entries live |
| `/ask MESSAGE` | Free-form question routed to the Claude bridge |
| `/approve APRV-...` | Approve a queued trade |
| `/reject APRV-... reason` | Reject a queued trade |
| `/settings` | Safe settings dump (no secrets) |

Security: messages from chat IDs not in `TELEGRAM_CHAT_ID ∪ TELEGRAM_ALLOWED_CHAT_IDS` are silently dropped (logged to `data/telegram-events.jsonl`).

### Alerts the agency sends automatically

Workflow start, mode change, Binance sync result, manual position detected, trade proposal, risk approval/rejection, live order placed, entry filled, stop placed, TP hit, partial exit, full exit, emergency exit, trade closed (with full summary), daily summary, safety warnings, API failures, position mismatches.

---

## 11. Every CLI — quick reference

### Cycle runners

| CLI | Purpose |
|---|---|
| `scripts.run_paper_cycle` | Paper mode — full pipeline, simulated fills. |
| `scripts.run_live_cycle` | Semi-auto live. Notional > threshold queues for approval. |
| `scripts.run_full_auto_cycle` | Full-auto live. Strict caps. Mandatory `--i-understand-this-fires-trades-without-asking`. |
| `scripts.trade_workflow_runner` | Mode-aware unified entrypoint — picks the right cycle. |

### Position management

| CLI | Purpose |
|---|---|
| `scripts.run_watch_positions` | One watcher tick, or `--loop --interval 60`. |
| `scripts.run_reconcile` | Compare `data/open-positions.json` to Binance. `--loop` for continuous. |
| `scripts.binance_position_sync` | Fetch + persist Binance positions. `--notify-telegram` for manual alerts. |
| `scripts.run_emergency_close` | Close every Binance position (reduce-only). Mandatory `--i-understand`. |

### Safety + approvals

| CLI | Purpose |
|---|---|
| `scripts.run_safety_reset` | `--status` / `--pause` / `--resume` / `--reset-daily`. |
| `scripts.run_approvals` | `--list` / `--inline` / `--approve` / `--reject` / `--expire` / `--prune`. |

### Analysis

| CLI | Purpose |
|---|---|
| `scripts.run_backtest` | Walk-forward backtest a symbol. |
| `scripts.run_learning_report` | Aggregate journal → insights. `--persist` writes `memory/learning-insights.md`. |
| `scripts.mode_manager` | `--status` / `--set paper` / `--set live`. |

### Telegram

| CLI | Purpose |
|---|---|
| `scripts.telegram_bot` | `--get-me` / `--register` / `--poll` / `--poll-once`. |

Each CLI accepts `--help` for its full flag set.

---

## 12. File layout — what writes where

```
binance-futures-ai-agency/
├── CLAUDE.md                    # root playbook for Claude Code
├── wiki.md                      # this file
├── .claude/
│   ├── agents/                  # 18 Claude Code subagent definitions
│   └── commands/                # 16 slash commands
├── agency/                      # 15 policy files (rules, workflows, templates)
├── agents/                      # 18 detailed agent folders, each with
│                                #   {agent,memory,skill}.md
├── scripts/                     # 49 Python modules + CLIs
├── tests/                       # 25 test files (198 tests)
├── tools/run_offline_tests.py   # stdlib-only test runner
├── config/                      # 8 example config files
├── data/                        # 12 runtime state files (writes happen here)
└── memory/                      # 9 append-only journals (writes happen here)
```

### `data/` (mutated by the runtime)

| File | Owner | Contents |
|---|---|---|
| `agency-state.json` | Cycle CLIs | Phase / mode / last cycle status |
| `mode-state.json` | `mode_manager` | Resolved effective mode |
| `system-health.json` | Safety Agent | Paused flag, paused reason |
| `risk-state.json` | `safety_state` | Daily PnL, consecutive losses, pause state |
| `open-positions.json` | `positions_store` | Agency-managed positions (atomic writes) |
| `synced-binance-positions.json` | `binance_position_sync` | Last Binance snapshot |
| `manual-positions.json` | `binance_position_sync` | Positions opened on Binance outside the agency |
| `pending-approvals.json` | `pending_approvals` | Queue for trades > $50 notional |
| `active-signals.json` | Cycle CLIs | In-flight proposals |
| `telegram-state.json` | `telegram_bot` | Bot init flag, last poll offset |
| `trade-events.jsonl` | Journal Agent | Machine-readable mirror of trade events |
| `telegram-events.jsonl` | `telegram_bot` | Send/recv events, unauthorized attempts |

### `memory/` (append-only, human-readable)

| File | Contents |
|---|---|
| `trade-journal.md` | Every executed trade (paper or live) |
| `rejected-trades.md` | Every proposal Risk Manager / Safety blocked |
| `safety-events.md` | Every pause / resume / emergency close |
| `execution-errors.md` | API errors + their resolution |
| `learning-insights.md` | Recommendations from the Learning Agent |
| `user-rules.md` | Permanent user instructions |
| `token-memory.md`, `strategy-memory.md`, `market-regime-memory.md` | Per-symbol / per-strategy / per-regime knowledge |

### `agency/` (read-only policy)

| File | Subject |
|---|---|
| `context.md` | What the agency is and why |
| `workflow.md` | The 15-step end-to-end workflow |
| `safety-rules.md` | Pause conditions + Phase 5/6 caps + approval threshold |
| `risk-rules.md` | Risk Manager defaults + rejection conditions |
| `execution-rules.md` | Binance secret handling + order requirements |
| `live-mode-policy.md` | Paper vs live vs live-readiness-only |
| `binance-sync-policy.md` | When + what to sync |
| `manual-position-policy.md` | How to handle manually-opened Binance positions |
| `profit-protection-policy.md` | Profit-seeking + loss-control rules |
| `telegram-control-policy.md` | Bot usage + auth |
| `telegram-templates.md` | Alert message formats |
| `memory-policy.md`, `learning-policy.md` | What to remember, when to act on insights |
| `no-trade-engine.md` | When to NOT trade |
| `communication-protocol.md` | Inter-agent message format |

---

## 13. Safety rails — what cannot be turned off

These are baked into the code. There is no env var or flag that disables them.

1. **API key + secret read only from env vars.** Never accepted as constructor args, never logged, never echoed back. Tested in `tests/test_env_loader.py`.
2. **Default mode is `paper`.** Invalid `MODE` always falls back to paper.
3. **Live execution requires `MODE=live` AND `ALLOW_LIVE_EXECUTION=true`.** Either alone is not enough.
4. **Withdrawal-permission check.** `scripts/account.py::check_permissions()` queries `/sapi/v1/account/apiRestrictions`. If the key has `enableWithdrawals=true`, all signed calls are refused. If the spot endpoint is unreachable, withdrawal status is treated as UNKNOWN and trading is still refused (fail-safe).
5. **Reduce-only on every exit.** `live_execution.close_position_market`, `place_stop_market`, `place_take_profit_market` always pass `reduceOnly=True`. There is no override.
6. **Stop fills first.** If a single bar's range covers both stop and TP, the exit simulator assumes the stop fills first. Backtests can't fool themselves with optimistic outcomes.
7. **Emergency close requires `--i-understand`.** No accidents from Ctrl-Tab.
8. **Full-auto requires `--i-understand-this-fires-trades-without-asking`.** Same idea, more explicit verb.
9. **Profit protection never widens stops, averages down, or hides losses.** `tests/test_profit_protection.py::test_never_recommend_widening_stop_or_averaging_down` enforces.
10. **HMAC-SHA256 signature verified against Binance's published test vector** in `tests/test_binance_signed_client.py`.

---

## 14. Troubleshooting

### "ALL GREEN" doesn't appear from `tools/run_offline_tests.py`

Check Python version (`python --version` should be ≥ 3.10). The runner uses match-statements and PEP 604 type unions.

### `mode_manager --status` shows `effective_mode: live-readiness-only`

You set `MODE=live` but at least one precondition is missing. Check the `blockers` array in the output. Common ones:

- `ALLOW_LIVE_EXECUTION=false` → set to `true`.
- `BINANCE_API_KEY / BINANCE_API_SECRET missing` → export both.
- `Telegram credentials missing` → only fires if `REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER=true`.

### `permission preflight FAILED — refusing to trade`

The agency probed your API key's permissions and found one of:

- The key has withdrawal permission enabled. **Disable withdrawals on the key in Binance's API management page**, then retry.
- The spot `/sapi/v1/account/apiRestrictions` endpoint isn't reachable with this key. The agency treats unknown withdrawal status as unsafe. Either grant the key minimal spot permission so the probe works, or accept the conservative refusal.

### Cycle exits with "trading paused"

`data/risk-state.json` says `trading_paused=true`. Check the reason:

```bash
python -m scripts.run_safety_reset --status
```

Resume only after you've fixed the root cause:

```bash
python -m scripts.run_safety_reset --resume --reason "verified BTC stable, position-manager clean"
```

If a cooldown is in place (after consecutive-loss breach), you can wait — the next cycle will auto-resume once the deadline passes.

### Telegram bot doesn't reply

```bash
python -m scripts.telegram_bot --get-me      # confirms token works
python -m scripts.telegram_bot --register    # re-registers commands
python -m scripts.telegram_bot --poll-once   # one polling pass
```

If `--get-me` fails: the token is wrong.
If `--get-me` works but `--poll-once` returns 0 updates: send a message to the bot first; long polling only sees updates from after you set up the webhook/started polling.

### Manual position keeps appearing as "missing_locally"

That's intentional — the agency is telling you there's a Binance position that has no internal `proposal_id`. Either:

- Close the position manually on Binance, or
- Set `ALLOW_AUTO_CLOSE_MANUAL_POSITIONS=true` if you want the agency to manage it.

### Backtest says `insufficient candles`

Reduce `--bars` or `--warmup`. The backtester needs at least `warmup_bars + 5` candles.

### `Binance API not reachable` warnings

`scripts/binance_client.py` retries with exponential backoff. If you see this once, ignore it. If you see it repeatedly, check your network / Binance's status page.

---

## 15. Tests

```bash
# Stdlib-only runner (recommended — no pytest install needed):
python tools/run_offline_tests.py
# → 198 unit tests + Phase 2/3/5/6 synthetic pipelines

# Or with pytest installed:
pytest tests/ -v

# Opt-in live smoke tests (hits Binance public API):
BINANCE_LIVE_TESTS=1 pytest tests/test_smoke_live.py -v
```

Coverage by module:

| Module | Test file |
|---|---|
| `symbol_filters` | `test_symbol_filters.py` (15 tests) |
| `indicators` | `test_indicators.py` (16) |
| `risk_engine` | `test_risk_engine.py` (13) |
| `paper_execution` | `test_paper_execution.py` (8) |
| `positions_store` | `test_positions_store.py` (7) |
| `exit_simulator` | `test_exit_simulator.py` (12) |
| `backtester` | `test_backtester.py` (2) |
| `learning` | `test_learning.py` (4) |
| `binance_signed_client` | `test_binance_signed_client.py` (9) |
| `live_execution` | `test_live_execution.py` (12) |
| `position_manager` | `test_position_manager.py` (8) |
| `emergency_close` | `test_emergency_close.py` (4) |
| `approval_policy` | `test_approval_policy.py` (11) |
| `pending_approvals` | `test_pending_approvals.py` (8) |
| `execution_router` | `test_execution_router.py` (7) |
| `safety_state` | `test_safety_state.py` (14) |
| `limits` | `test_limits.py` (8) |
| `env_loader` | `test_env_loader.py` (12) |
| `mode_manager` | `test_mode_manager.py` (6) |
| `profit_protection` | `test_profit_protection.py` (9) |
| `telegram_commands` + `telegram_bot` | `test_telegram_commands.py` (9) |
| `binance_position_sync` | `test_binance_position_sync.py` (4) |

Plus 4 synthetic end-to-end pipelines in `tools/run_offline_tests.py` covering Phases 2 / 3 / 5 / 6.

---

## 16. Glossary

- **Agency Orchestrator** — coordinates all agents per the workflow in `agency/workflow.md`.
- **Approval threshold** — notional USDT above which `SEMI_AUTO_LIVE` queues for user approval. Default $50.
- **Cycle** — one pass through scan → research → strategy → risk → execution → journal.
- **Effective mode** — what `mode_manager` resolved given env state. One of `paper`, `live-readiness-only`, `live-enabled`.
- **Manual position** — a Binance position the agency didn't open (no internal `proposal_id`).
- **MFE / MAE** — max favorable / adverse excursion, in unrealized PnL terms.
- **Mismatch** — internal state ≠ Binance state. Position Manager pauses on any mismatch.
- **Pending approval** — a queued proposal in `data/pending-approvals.json` waiting for the user.
- **Reduce-only** — Binance order flag that prevents the order from increasing position size. Always `True` on exits.
- **Reconciliation** — comparing `data/open-positions.json` to `/fapi/v2/positionRisk`.
- **Risk Manager** — agent with veto power over trades. Approves / rejects / reduces size / lowers leverage.
- **Safety Agent** — agent with highest authority. Pauses trading, blocks execution, triggers emergency exit.
- **Watcher** — agent that monitors open positions every tick.

---

That's the whole thing. If something here is wrong or unclear, fix the file directly — `wiki.md` is the canonical operating reference and should always match what the code does.
