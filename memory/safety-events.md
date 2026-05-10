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
