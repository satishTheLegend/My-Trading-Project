# Monitor Open Positions

Trigger the Watcher Agent (and Exit Agent when appropriate) for all currently open Binance Futures positions.

Arguments:
`$ARGUMENTS`

## Required Steps

1. Read `data/open-positions.json` (if it exists).
2. Reconcile with Binance state via Position Manager Agent.
3. For each open position, invoke the Watcher Agent.
4. If the Watcher Agent recommends `take_profit`, `tighten_stop`, `exit_recommended`, or `emergency_exit`, hand off to the Exit Agent.
5. Exit Agent uses reduce-only orders through the Execution Agent.
6. Journal Agent records every action.
7. User Report Agent summarizes.

## Safety

- Never open new positions from this command.
- If protective orders are missing, immediately escalate to Safety Agent.
- If data is stale or API is unreachable, do not act blindly — alert the user.

## Output

```json
{
  "positions_checked": 0,
  "actions_taken": [],
  "warnings": [],
  "next_check_in_seconds": 0
}
```
