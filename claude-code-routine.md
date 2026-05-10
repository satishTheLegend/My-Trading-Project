# Running the Agency with Claude Code

This is the daily-driver guide for operating the agency through Claude Code.
The project was designed for Claude Code — that's why it has
`.claude/agents/` (subagents), `.claude/commands/` (slash commands), and
`CLAUDE.md` (the playbook Claude reads on every session).

For raw CLI usage (no Claude Code), see `wiki.md`. For the system architecture, see `agency/workflow.md`.

## Session Context

Every session reads and writes `memory/session-context.md` automatically via `.claude/settings.json` hooks:

- **SessionStart hook**: prints current safety state + session context to give Claude instant situational awareness.
- **Stop hook**: runs `run_reconcile` after every response to keep position state fresh.

At the end of each trading cycle, the orchestrator or user-report-agent updates `memory/session-context.md` with:
- What happened this session (trades, decisions, fixes)
- What still needs attention (open issues, unresolved positions)
- Safety state snapshot
- Environment variable status
- Instructions for the next session

**Read `memory/session-context.md` at the start of every session** — it is the fastest path to understanding where the agency left off.

## Contents

1. [One-time setup](#1-one-time-setup)
2. [How Claude Code uses this project](#2-how-claude-code-uses-this-project)
3. [Daily routine — the 3 sessions](#3-daily-routine--the-3-sessions)
4. [The slash commands](#4-the-slash-commands)
5. [Talking to specific agents](#5-talking-to-specific-agents)
6. [Promotion path: paper → testnet → semi-auto → full-auto](#6-promotion-path-paper--testnet--semi-auto--full-auto)
7. [Hooks for automation](#7-hooks-for-automation)
8. [Permissions + settings](#8-permissions--settings)
9. [Patterns that work well](#9-patterns-that-work-well)
10. [Anti-patterns to avoid](#10-anti-patterns-to-avoid)

---

## 1. One-time setup

### Install Claude Code

```bash
# macOS / Linux:
curl -fsSL https://claude.ai/install.sh | bash
# or via npm:
npm install -g @anthropic-ai/claude-code
```

After install, run `claude /login` to authenticate.

### Open the project

```bash
cd ~/Documents/Claude/Projects/My-Trading-Project
claude
```

Claude Code will read `CLAUDE.md` automatically on session start. That file is the system prompt — it teaches Claude the trading philosophy, agent authority order, and global rules.

### Set environment variables

Claude Code respects your shell's environment. Either:

```bash
# Option A: source a .env before launching claude
set -a; source .env; set +a
claude

# Option B: per-command env (safer for secrets)
BINANCE_API_KEY=... BINANCE_API_SECRET=... claude
```

**Never paste API keys into the Claude Code chat.** The agency reads them only from environment variables — that's enforced in code (`scripts/env_loader.py`). If you paste a secret in chat, it ends up in your conversation history.

### Quick sanity check

In Claude Code, type:

```
/verify-agency
```

That runs `.claude/commands/verify-agency.md`, which audits the project structure and reports any drift. You should get back a JSON report saying everything is green.

---

## 2. How Claude Code uses this project

Three layers, each with its own purpose:

### Layer 1: CLAUDE.md (the system prompt)

Read by Claude on every session. Contains:
- Trading philosophy (capital survival > profit)
- Global safety rules (15 of them)
- Default operating mode (paper)
- Agent authority order
- Standard message + trade-proposal + risk-approval formats

You don't interact with this directly — Claude just reads it.

### Layer 2: `.claude/agents/` (the 18 subagents)

Each is a specialist Claude can delegate to with its own context window. When you ask Claude to do something trading-related, it routes the work to the right subagent based on the agent's `description` field.

Example: you say *"check for manual positions on Binance"* — Claude reads the description on `binance-sync-agent.md` ("MUST BE USED... when manual Binance positions may exist...") and delegates there.

You can also explicitly request an agent:

> Use the **risk-manager-agent** to evaluate a proposed long on DOGEUSDT at 0.07654 with stop 0.07500.

### Layer 3: `.claude/commands/` (the 16 slash commands)

Structured workflows you trigger by typing `/<name>` in chat. Each command is a markdown file that tells Claude exactly which agents to invoke and in what order.

Layered together: you type a slash command → it tells Claude to coordinate several subagents → those subagents call into Python scripts when they need to actually fetch market data or place orders.

---

## 3. Daily routine — the 3 sessions

This is the recommended cadence for paper / semi-auto live trading.

### Morning session (5–10 min)

```
/start-trading-workflow
```

What this does:
1. Reads `CLAUDE.md`, `agency/workflow.md`, `agency/safety-rules.md`.
2. Asks the **safety-kill-switch-agent** if trading is allowed.
3. Asks the **market-intelligence-agent** for BTC/ETH bias.
4. Runs the **token-screener-agent** + **token-research-agent** + **strategy-agent** + **trade-decision-agent** + **risk-manager-agent**.
5. Calls into `scripts/run_paper_cycle.py` (paper) or `scripts/run_live_cycle.py` (semi-auto).
6. Returns a structured workflow report.

After this, follow-up with:

```
Show me the trade journal for today.
```

Claude pulls from `memory/trade-journal.md`.

### Mid-day check-in (1 min)

```
/monitor-open-positions
```

This delegates to the **watcher-agent** which:
- Loads `data/open-positions.json`.
- Fetches latest 1m candles for each symbol.
- Updates mark-to-market PnL + MFE/MAE.
- Decides hold / partial TP / trail stop / exit.
- Journals closures.

If you also want manual-position visibility:

```
/sync-binance
```

Routes to the **binance-sync-agent** → calls `scripts/binance_position_sync.py`.

### End-of-day session (10 min)

```
/daily-report
```

What you'll see:
- Market regime summary
- Tokens screened / rejected
- Trades created / approved / rejected / executed
- Net PnL, fees, funding
- Open positions snapshot
- Safety events (any pauses today?)
- Pending learning insights

Follow-up:

```
Generate a learning report and persist insights.
```

Claude calls `scripts/run_learning_report.py --persist`. New insights land in `memory/learning-insights.md` for you to approve or reject tomorrow.

---

## 4. The slash commands

| Command | What you'd say in plain English | What it does |
|---|---|---|
| `/start-trading-workflow` | "Run a full cycle" | Coordinates all 16 agents through the standard 15-step workflow |
| `/paper-trade-cycle` | "Run paper trading" | Same but explicitly paper, no real orders |
| `/live-trade-cycle` | "Run live trading" | Same but live — only fires if all safety preconditions pass |
| `/monitor-open-positions` | "Check my positions" | Watcher tick |
| `/daily-report` | "How did today go?" | End-of-day summary |
| `/emergency-shutdown` | "Stop everything now" | Pauses + closes everything reduce-only |
| `/verify-agency` | "Is the project healthy?" | Audits structure |
| `/switch-mode` | "Switch to paper / live" | Inspect or change mode |
| `/live-readiness-check` | "Am I ready to go live?" | All 12 preconditions |
| `/telegram-setup` | "Set up the Telegram bot" | Token check, command registration, test message |
| `/sync-binance` | "Sync Binance state" | Wallet + positions + manual detection |
| `/status` | "What's the system status?" | Mode, wallet, positions, safety |
| `/positions` | "What's open?" | Agency + manual positions |
| `/pause` | "Pause trading" | Safety pause |
| `/resume` | "Resume trading" | Safety resume (with checks) |
| `/close-position DOGEUSDT` | "Close DOGE" | Reduce-only close one symbol |

Tip: type `/` in the Claude Code chat to see the full menu.

---

## 5. Talking to specific agents

When you know exactly which agent should handle something, name it. Claude follows the spec in that agent's `description` field.

```
Use the binance-sync-agent to detect any manual positions and update
data/manual-positions.json.
```

```
Have the risk-manager-agent evaluate this proposal:
  symbol DOGEUSDT, side LONG, entry 0.07654, stop 0.07500,
  TP 0.07900, leverage 3x, margin 2 USDT.
```

```
Ask the watcher-agent whether my open SHIBUSDT position should
take partial profit yet.
```

```
Use the safety-kill-switch-agent to pause trading for 4 hours
because I'm stepping away.
```

```
Have the journal-accounting-agent show me the last 5 trade entries
with mistake tags.
```

```
Use the learning-optimization-agent to surface any recurring
mistakes from the last 50 trades.
```

Claude will use the agent's specialised context, run the right Python script, and report back.

---

## 6. Promotion path: paper → testnet → semi-auto → full-auto

Claude Code helps you walk through the safety gates one at a time.

### Step 1: paper (week 1)

```
/paper-trade-cycle
```

Run this every morning for a week. Watch how the agents reason. Check the journal each evening. Build trust.

### Step 2: testnet (week 2)

```
Set MODE=live and ALLOW_LIVE_EXECUTION=true with my testnet keys.
Then run /live-readiness-check.
```

You'll need to set the env vars in your shell first (Claude can't touch your env). After the readiness check passes, run a real testnet cycle:

```
/live-trade-cycle
```

This actually places orders on the Binance testnet. Watch them fill, watch the watcher manage them.

### Step 3: semi-auto live (week 3)

Switch the keys to mainnet (`BINANCE_TESTNET=false`). Same `/live-trade-cycle`. Now real money is on the line, but the $50 approval threshold means anything bigger pauses for your review:

```
/live-trade-cycle
```

When trades queue:

```
Show me the pending approvals.
```

Claude runs `python -m scripts.run_approvals --list`. You decide:

```
Approve APRV-20260510-143000-DOGEUSDT-001
```

or

```
Reject APRV-20260510-143000-DOGEUSDT-001 because BTC just dumped 3%.
```

### Step 4: full-auto (week 4+, only if you're comfortable)

```
Run a full-auto live cycle with the default strict caps.
```

Claude calls `scripts/run_full_auto_cycle.py` with the mandatory `--i-understand-this-fires-trades-without-asking` flag. Use cron to run it on a cadence (the wiki has a sample). Use `/pause` whenever you need to step away.

---

## 7. Hooks for automation

Claude Code supports hooks that run on specific events — `SessionStart`, `Stop` (after each response), etc. They're declared in `.claude/settings.json`.

Useful hooks for this project:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python -m scripts.run_safety_reset --status"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python -m scripts.run_reconcile --no-permission-check 2>/dev/null || true"
          }
        ]
      }
    ]
  }
}
```

What this gives you:
- Every Claude session starts with a current safety-state snapshot in the context.
- After every Claude response, a quick reconciliation tick runs in the background — so if your local state ever drifts from Binance, you'll know on the next reply.

Hooks run with whatever environment the parent `claude` process inherited, so they see your `BINANCE_API_KEY` etc.

---

## 8. Permissions + settings

Claude Code asks before running new commands. To pre-approve the agency's CLIs, add them to `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python -m scripts.run_paper_cycle:*)",
      "Bash(python -m scripts.run_watch_positions:*)",
      "Bash(python -m scripts.run_backtest:*)",
      "Bash(python -m scripts.run_learning_report:*)",
      "Bash(python -m scripts.binance_position_sync:*)",
      "Bash(python -m scripts.run_reconcile:*)",
      "Bash(python -m scripts.run_safety_reset:*)",
      "Bash(python -m scripts.run_approvals:*)",
      "Bash(python -m scripts.mode_manager:*)",
      "Bash(python -m scripts.telegram_bot:*)",
      "Bash(python tools/run_offline_tests.py:*)",
      "Read(memory/*)",
      "Read(data/*)",
      "Edit(memory/user-rules.md)"
    ],
    "ask": [
      "Bash(python -m scripts.run_live_cycle:*)",
      "Bash(python -m scripts.run_full_auto_cycle:*)",
      "Bash(python -m scripts.run_emergency_close:*)"
    ],
    "deny": [
      "Bash(rm:*)",
      "Bash(git push:*)"
    ]
  }
}
```

The `ask` list is intentionally restrictive — anything that places real orders prompts you for confirmation every time. Don't move those to `allow`.

The `deny` list prevents Claude from ever pushing your `.env` to a remote or deleting safety-event journals.

---

## 9. Patterns that work well

### Conversational mode

Just describe what you want. Claude will pick the right agent + script.

> "I haven't traded in 3 days. Sync Binance, show me what positions are open, and tell me if any need attention."

Claude will:
1. Use **binance-sync-agent** → call `scripts/binance_position_sync.py`.
2. Use **position-manager-agent** → load `data/open-positions.json` + `data/manual-positions.json`.
3. Use **watcher-agent** → assess each open position.
4. Summarize.

### Pinpoint mode

Skip the orchestration when you know what you want.

> "Run `python -m scripts.run_backtest --symbol DOGEUSDT --interval 1h --bars 500 --verbose-trades`"

Claude runs it. No agent delegation overhead.

### Audit mode

Ask Claude to read journals + reason about them.

> "Read memory/trade-journal.md and tell me which strategy has the worst win rate over the last 20 trades."

Claude will use the **learning-optimization-agent** + raw file reads to answer. This is a lot more useful than just running the learning report — Claude can spot patterns the rule-based learner misses.

### What-if mode

> "What would happen if I set the approval threshold to $25 instead of $50? Walk through the logic in execution_router.py."

Claude reads the file and explains. No code change happens unless you ask for it.

---

## 10. Anti-patterns to avoid

### Do not paste API keys into chat

The agency reads them from env vars. Pasting them into chat:
- Stores them in your conversation history.
- Bypasses the redaction in `scripts/env_loader.py::_Secrets.__repr__`.
- Risks them being included in any export / share.

### Do not let Claude bypass the safety preconditions

If `/live-readiness-check` reports blockers, **fix them before running `/live-trade-cycle`**. Don't tell Claude "ignore the warning and run it anyway" — the underlying scripts will refuse, and you'll just be fighting the system.

### Do not run full-auto without watching for the first few cycles

Even after `/live-readiness-check` passes, sit with full-auto for the first 3-5 cycles. Watch the cycle reports + journal entries. Use `/pause` if anything looks off.

### Do not edit `data/risk-state.json` by hand

Use `scripts.run_safety_reset --resume` / `--reset-daily`. The store has atomic-write logic; hand-editing can leave it in a half-state.

### Do not delete `memory/safety-events.md`

It's the audit trail for every pause + emergency close. The Learning Agent uses it to spot recurring failure modes.

---

## A typical week

| Day | Activity | Slash command |
|---|---|---|
| Mon morning | Review weekend, scan market | `/start-trading-workflow` |
| Mon midday | Check open positions | `/monitor-open-positions` |
| Mon evening | Daily report + learning | `/daily-report` |
| Tue–Thu | Same routine, paper or semi-auto | same |
| Fri evening | Weekly review | "Read trade-journal.md and give me a weekly post-mortem" |
| Sat | Backtest improvements | "Backtest DOGEUSDT, BNXUSDT, and SHIBUSDT over the last 1000 1h bars and compare" |
| Sun | Plan + maintenance | `/verify-agency`, review `memory/learning-insights.md`, approve / reject pending insights |

That's the rhythm. The agency is designed to need attention at predictable points — not a dashboard you have to babysit.

---

## Companion docs

- `wiki.md` — full operating reference (env vars, all CLIs, file layout, safety rails)
- `CLAUDE.md` — the system prompt Claude reads on every session
- `agency/workflow.md` — the 15-step end-to-end workflow
- `scripts/README.md` — per-module quick-start
