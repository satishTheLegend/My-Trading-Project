# Daily Report

Produce the end-of-day report for the user.

Arguments:
`$ARGUMENTS`

## Required Steps

1. Read `memory/trade-journal.md`.
2. Read `memory/rejected-trades.md`.
3. Read `memory/safety-events.md`.
4. Read `memory/learning-insights.md`.
5. Aggregate by date (default: today; user may pass a date in `$ARGUMENTS`).
6. Use the User Report Agent to produce the report.
7. Use the Learning Agent to surface any approval-required recommendations.

## Report Sections

- Mode and uptime.
- Market regime summary.
- Tokens screened and rejected (counts).
- Trade proposals: created / approved / rejected.
- Trades executed: count, win rate, gross PnL, fees, funding, net PnL.
- Open positions snapshot.
- Safety events.
- Learning insights pending user approval.
- Tomorrow's posture (preferred direction, watchlist, no-trade triggers active).

## Style

Clear, direct, structured. No hype. Honor user reporting preferences in `memory/user-rules.md`.
