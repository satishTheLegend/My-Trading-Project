# Live Trade Cycle

Run the Binance Futures Trading Agency in live mode only if safe.

Arguments:
`$ARGUMENTS`

## Required Checks

1. Read `CLAUDE.md`.
2. Confirm the user explicitly requested live mode.
3. Confirm trading mode is `SEMI_AUTO_LIVE` or `FULL_AUTO_LIVE`.
4. Confirm API credentials are not in prompt or code.
5. Confirm API key has no withdrawal permission.
6. Use Safety/Kill-Switch Agent.
7. Use Risk Manager Agent.
8. Use Execution Agent only after approval.

## If Unsafe

Do not execute.
Switch to paper mode or ask for user correction.

## If Safe

Run full workflow:
Safety → Market → Screening → Research → Strategy → Decision → Risk → Sizing → **Execution Router** → Watcher → Exit → Journal → Learning → Report.

## SEMI_AUTO_LIVE Routing (Phase 5)

Use `python -m scripts.run_live_cycle --i-understand-this-is-real-money [--approval-threshold N]`.

The Execution Router (`scripts/execution_router.py`) decides per proposal:

- Notional ≤ approval threshold (default **50 USDT**) → auto-fire through `scripts/live_execution.py`.
- Notional > threshold → queue in `data/pending-approvals.json`, return without firing.

Approve queued items with:

- `python -m scripts.run_approvals --list`
- `python -m scripts.run_approvals --inline` (interactive y/N per entry)
- `python -m scripts.run_approvals --approve <APPROVAL_ID>`
- `python -m scripts.run_approvals --reject <APPROVAL_ID> --reason "..."`

The next `run_live_cycle.py` invocation picks up entries marked `approved` and fires them through `live_execution`. Entries past their `deadline_at` are auto-`expired`.

Defensive overrides that **always** queue (regardless of notional):
- First live trade of a process lifetime.
- Daily loss already consumed ≥ 75% of the daily-loss limit.

## FULL_AUTO_LIVE (Phase 6)

`python -m scripts.run_full_auto_cycle.py --i-understand-this-fires-trades-without-asking [...caps]`

Same router, but every Risk-Manager-approved + Safety-Agent-cleared trade fires automatically. Strict caps enforced between proposals via `scripts/safety_state.py` + `scripts/limits.py`:

- daily-loss limit (default 1.5 USDT) → pauses until UTC midnight or manual resume
- consecutive-loss limit (default 3) → pauses with 60-min cooldown
- max-open-positions (default 2)
- no-duplicate-symbol
- per-cycle-trade-cap (default 5)

Daily rollover at UTC midnight zeroes counters and clears soft pauses. Hard pauses (e.g., position-manager mismatch) carry over.

Manual safety ops:
- `python -m scripts.run_safety_reset --status`
- `python -m scripts.run_safety_reset --resume --reason "..."`
- `python -m scripts.run_safety_reset --reset-daily`
- `python -m scripts.run_safety_reset --pause --reason "..." --until-minutes N`
