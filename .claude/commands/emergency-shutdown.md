# Emergency Shutdown

Immediately trigger the Safety/Kill-Switch Agent.

Arguments:
`$ARGUMENTS`

Actions (in order):

1. Pause all new trades (`python -m scripts.run_safety_reset --pause --reason "$ARGUMENTS"`).
2. Sync Binance positions (`python -m scripts.binance_position_sync`).
3. Identify agency-managed and manual positions.
4. Check liquidation risk and protection-order status.
5. If emergency close is required, route through the Exit Agent + Execution Agent with `reduceOnly=True` via `python -m scripts.run_emergency_close --i-understand --reason "$ARGUMENTS"`.
6. Notify Telegram with the Safety Pause template plus per-position close summaries.
7. Journal a Safety Event for every action.

Never open new trades during emergency shutdown.
