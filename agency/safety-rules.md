# Safety Rules

Safety Agent has highest authority.

## Immediate Pause Conditions

Pause new trading if:
- API disconnected.
- WebSocket disconnected during open position.
- Data stale.
- Daily loss limit reached.
- Consecutive loss limit reached.
- Wallet below threshold.
- Stop-loss missing.
- Position state mismatch.
- Binance rejects protective order.
- Liquidation price too close.
- BTC violent move.
- Market news shock.
- Unknown error in execution.
- User requests pause.

## Emergency Exit Conditions

Trigger emergency exit if:
- Position is open without protection.
- Liquidation distance becomes dangerous.
- API state confirms unexpected position.
- Stop-loss order disappeared.
- Monitoring data becomes unreliable and position risk is high.
- Account balance drops unexpectedly.
- Binance reports margin risk.

## Secret Handling

Never print API keys.
Never commit API keys.
Never store API keys in memory files.
Use environment variables only.
Reject live execution if secrets are exposed.

## Live Mode Safety

Full auto live mode requires:
- Explicit user instruction.
- Secure API setup.
- Risk config.
- Safety config.
- Tested execution script.
- Tested emergency close script.

## Semi-Auto Live Approval Rule (Phase 5)

In `SEMI_AUTO_LIVE` the Execution Router enforces a notional threshold:

- Notional ≤ **50 USDT** → auto-fire after Risk Manager + Safety Agent approval.
- Notional > 50 USDT → queue in `data/pending-approvals.json`, return cleanly, wait for the user to run `python -m scripts.run_approvals --inline` (or `--approve <id>`) before the order fires.

Defensive overrides that **always** queue, regardless of notional:
- First live trade of a process lifetime (catches typos / new symbols on day one).
- Daily loss already consumed ≥ 75% of the daily-loss limit.

Things that are **flagged in the journal but do NOT by themselves queue**:
- Leverage above the configured `flag_high_leverage_above` (default 5x). Risk Manager already capped leverage; this just makes high-leverage approvals visible after the fact.

The threshold is configurable per cycle via `run_live_cycle.py --approval-threshold N`. Tighten it in volatile markets; lower it for very small accounts.

## Full-Auto Live Strict Caps (Phase 6)

`FULL_AUTO_LIVE` skips per-trade approval entirely but enforces hard caps on every cycle via `scripts/safety_state.py` + `scripts/limits.py`. The caps also apply to `SEMI_AUTO_LIVE` — they're orthogonal to the approval threshold, not a replacement.

### Strict Caps (defaults; CLI-configurable)

- **Daily loss limit**: 1.5 USDT (≈15% of a 10-USDT wallet). Breach pauses trading until UTC midnight or `run_safety_reset --resume`.
- **Consecutive loss limit**: 3 losses in a row. Breach pauses with a 60-minute cooldown that auto-clears.
- **Max open positions**: 2.
- **No duplicate symbol positions**.
- **Per-cycle trade cap**: 5 fires per cycle.

Hard caps (`paused`, `daily_loss_limit`, `consecutive_loss_limit`, `per_cycle_trade_cap`) abort the rest of the cycle on breach. Soft caps (`max_open_positions`, `no_duplicate_symbol`) skip just the offending proposal.

### Daily Rollover

At the start of every cycle, `SafetyStateManager.perform_daily_rollover_if_needed()` archives yesterday's stats and zeros today's counters when the UTC date has changed. Pauses auto-clear on rollover *unless* flagged `pause_carry_over_rollover` (used for hard incidents like withdrawal-permission detection or position-manager mismatch).

### Manual Safety Ops

- `python -m scripts.run_safety_reset --status` — show current state.
- `python -m scripts.run_safety_reset --resume --reason "..."` — clear pause.
- `python -m scripts.run_safety_reset --reset-daily` — force rollover.
- `python -m scripts.run_safety_reset --pause --reason "..." --until-minutes 480` — manual pause window.

Every manual op writes a Safety Event to `memory/safety-events.md`.
