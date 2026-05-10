# Safety Events

Log of every Safety/Kill-Switch Agent action: pauses, emergency exits, blocked executions, daily-loss triggers, consecutive-loss triggers, withdrawal-permission detections, etc.

## Format

```
## SAFETY-YYYYMMDD-N

- timestamp:
- mode:
- event_type: pause_new_trades | force_paper_mode | block_execution | emergency_exit | api_disconnect | data_stale | stop_missing | daily_loss_hit | consecutive_loss_hit | withdrawal_permission_detected | other
- triggered_by: safety-agent | watcher-agent | execution-agent | user
- details:
- positions_affected: []
- action_taken:
- duration_minutes:
- resolved_at:
- resolution_notes:
```

## SAFETY-20260510-142559

- timestamp: 2026-05-10T14:25:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-10T14:25:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-142559

- timestamp: 2026-05-10T14:25:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-10T14:25:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-142559

- timestamp: 2026-05-10T14:25:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T14:25:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-142559

- timestamp: 2026-05-10T14:25:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T14:25:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-144053

- timestamp: 2026-05-10T14:40:53Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-10T14:40:53Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-144053

- timestamp: 2026-05-10T14:40:53Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-10T14:40:53Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-144053

- timestamp: 2026-05-10T14:40:53Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T14:40:53Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-144053

- timestamp: 2026-05-10T14:40:53Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T14:40:53Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-145548

- timestamp: 2026-05-10T14:55:48Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-10T14:55:48Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-145548

- timestamp: 2026-05-10T14:55:48Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-10T14:55:48Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-145548

- timestamp: 2026-05-10T14:55:48Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T14:55:48Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-145548

- timestamp: 2026-05-10T14:55:48Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T14:55:48Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-145624

- timestamp: 2026-05-10T14:56:24Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-10T14:56:24Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-145624

- timestamp: 2026-05-10T14:56:24Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-10T14:56:24Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-145624

- timestamp: 2026-05-10T14:56:24Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T14:56:24Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-145624

- timestamp: 2026-05-10T14:56:24Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T14:56:24Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-153617

- timestamp: 2026-05-10T15:36:17Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-10T15:36:17Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-153617

- timestamp: 2026-05-10T15:36:17Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-10T15:36:17Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-153617

- timestamp: 2026-05-10T15:36:17Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T15:36:17Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-153617

- timestamp: 2026-05-10T15:36:17Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T15:36:17Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-153758

- timestamp: 2026-05-10T15:37:58Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-10T15:37:58Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-153758

- timestamp: 2026-05-10T15:37:58Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-10T15:37:58Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-153758

- timestamp: 2026-05-10T15:37:58Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T15:37:58Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-153758

- timestamp: 2026-05-10T15:37:58Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T15:37:58Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-155036

- timestamp: 2026-05-10T15:50:36Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-10T15:50:36Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-155036

- timestamp: 2026-05-10T15:50:36Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-10T15:50:36Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-155036

- timestamp: 2026-05-10T15:50:36Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T15:50:36Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-155036

- timestamp: 2026-05-10T15:50:36Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-10T15:50:36Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260510-170936

- timestamp: 2026-05-10T17:09:36Z
- mode: ANY
- event_type: manual_daily_reset
- triggered_by: user
- details: forced daily rollover; previous day daily_pnl=0 trades=0
- positions_affected: []
- action_taken: daily counters zeroed; pause cleared if not carry-over
- duration_minutes: 0
- resolved_at: 2026-05-10T17:09:36Z
- resolution_notes: run_safety_reset --reset-daily

## SAFETY-20260510-LIVE-WORKFLOW-001

- timestamp: 2026-05-10T00:00:00Z
- mode: SEMI_AUTO_LIVE
- event_type: block_execution
- triggered_by: safety-agent
- details: Full 15-step live workflow executed by orchestrator. Execution blocked by 4 simultaneous hard blocks: (1) Binance mainnet fapi.binance.com returns HTTP 451 geo-restriction from server, (2) BINANCE_TESTNET=true env causes all signed API calls to route to testnet.binancefuture.com which rejects mainnet keys with code=-2015, (3) MYSTERYUSDT residual position state unknown — emergency close script reported closed 0/1 residual 1 across all prior attempts, (4) Sandbox execution gate denied python -m scripts.run_live_cycle --i-understand-this-is-real-money at the Bash tool level.
- positions_affected: []
- action_taken: No orders placed. No capital at risk. Workflow completed all 15 steps with NO_TRADE decision. Journal updated. Learning insights INSIGHT-20260510-003 and INSIGHT-20260510-004 filed. Session context updated.
- duration_minutes: 0
- resolved_at: N/A — blocks still active
- resolution_notes: User must (1) verify MYSTERYUSDT on Binance Web UI, (2) either get testnet API keys for testnet trading or deploy on non-geo-restricted server for mainnet trading, (3) confirm BINANCE_TESTNET env matches intended exchange.
