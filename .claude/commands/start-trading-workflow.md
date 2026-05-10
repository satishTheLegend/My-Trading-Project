# Start Trading Workflow

You are starting the complete Binance Futures AI Trading Agency workflow.

Arguments from user:
`$ARGUMENTS`

## Mission

Trigger the full trading workflow using the Agency Orchestrator. The orchestrator must coordinate all relevant agents and run the correct workflow based on mode:

- PAPER_TRADING
- SEMI_AUTO_LIVE
- FULL_AUTO_LIVE

Default to PAPER_TRADING unless the user explicitly requests live mode and live mode is safely configured.

## Required First Steps

1. Read `CLAUDE.md`.
2. Read `agency/context.md`.
3. Read `agency/workflow.md`.
4. Read `agency/safety-rules.md`.
5. Read `agency/risk-rules.md`.
6. Check current mode in `data/agency-state.json` if available.
7. Check safety state in `data/system-health.json` if available.
8. Use the `agency-orchestrator` subagent proactively.

## Workflow

Ask the Agency Orchestrator to:

1. Confirm operating mode.
2. Confirm Binance connectivity only if implementation exists.
3. Confirm API key is not exposed and not logged.
4. Confirm whether live execution is allowed.
5. Trigger Safety/Kill-Switch Agent.
6. Trigger Market Intelligence Agent.
7. Trigger Token Screener Agent.
8. Trigger Token Research Agent.
9. Trigger Strategy Agent.
10. Trigger Trade Decision Agent.
11. Trigger Risk Manager Agent.
12. Trigger Position Sizing Agent.
13. Trigger Execution Agent only if approved and allowed.
14. Trigger Watcher Agent for open positions.
15. Trigger Journal Agent.
16. Trigger Learning Agent.
17. Trigger User Report Agent.

## Mandatory Safety

Do not execute a live order unless:
- The user has explicitly enabled live mode.
- Risk Manager approved the exact trade.
- Safety Agent permits new trades.
- Execution Agent verifies symbol, quantity, margin, leverage, precision, and protection.
- API credentials are secure in environment variables.
- No withdrawal permission is present.

If anything is uncertain, run PAPER_TRADING mode or SEMI_AUTO mode instead of FULL_AUTO_LIVE.

## Output

Return a structured agency status report:

```json
{
  "workflow_status": "",
  "mode": "",
  "market_regime": "",
  "tokens_screened": 0,
  "tokens_researched": 0,
  "trade_decision": "",
  "risk_status": "",
  "execution_status": "",
  "open_positions": [],
  "warnings": [],
  "next_actions": []
}
```
