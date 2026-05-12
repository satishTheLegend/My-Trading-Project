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

## SAFETY-20260511-081840

- timestamp: 2026-05-11T08:18:39Z
- mode: ANY
- event_type: manual_pause
- triggered_by: user
- details: user topping up wallet - no new trades until resumed
- positions_affected: []
- action_taken: trading paused until 2026-05-12T08:18:39Z
- duration_minutes: 1440
- resolved_at: 
- resolution_notes: run_safety_reset --pause

## SAFETY-20260511-081914

- timestamp: 2026-05-11T08:19:14Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T08:19:14Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-3

- timestamp: 2026-05-11T08:59:30Z
- mode: FULL_AUTO_LIVE
- event_type: stop_missing
- triggered_by: safety-agent (orchestrator post-execution verification)
- details: Cycle #4 fired BUSDT LONG via run_full_auto_cycle at 08:56:26Z (orderId 971834532, 18 qty @ 0.4514, margin 2.71, lev 3x). Post-fill verification found ZERO protective orders on exchange (openOrders for BUSDT empty, openAlgoOrders for BUSDT empty). Position was running naked with only a software-side stop record at 0.4264. Root cause: execution_router and run_full_auto_cycle never invoke live_execution.place_stop_market or place_take_profit_market after the entry fill - protective bracket placement is missing from the FULL_AUTO_LIVE pipeline. Secondary issue: live_execution.place_stop_market targets legacy /fapi/v1/order which is rejected with error -4120 since Binance migrated conditional orders to /fapi/v1/algoOrder on 2025-12-09.
- positions_affected: [POS-20260511-085626-BUSDT-001]
- action_taken: Orchestrator manually placed STOP_MARKET (algoId 3000001506269526, trigger 0.4264, reduceOnly, MARK_PRICE, priceProtect) and TAKE_PROFIT_MARKET (algoId 3000001506269544, trigger 0.5189, reduceOnly, MARK_PRICE, priceProtect) for full 18 qty via /fapi/v1/algoOrder. 33/33/33 scale-out was infeasible: BUSDT MIN_NOTIONAL is 5 USDT, slice of 6 qty * ~0.49 = ~2.9 fails the filter. Used single full-qty TP at TP2 (0.5189) to preserve locked R:R >= 2.0; Watcher must manage any further partial scaling.
- duration_minutes: ~3
- resolved_at: 2026-05-11T08:59:30Z
- resolution_notes: Protection now in place. Two follow-up tasks for error-fix agent: (1) wire execution_router/run_full_auto_cycle to call live_execution.place_stop_market and place_take_profit_market immediately after entry fill, before the cycle returns; (2) migrate live_execution conditional-order helpers to /fapi/v1/algoOrder (algoType=CONDITIONAL, triggerPrice instead of stopPrice, clientAlgoId instead of newClientOrderId). Add post-execution invariant check: if open position exists for a symbol with no reduce-only protective order, escalate to Safety Agent before cycle returns success. Add minNotional-aware scale-out planner: if any TP slice notional < MIN_NOTIONAL, fall back to fewer, larger TPs that preserve R:R, log the downgrade.

## SAFETY-20260511-095230

- timestamp: 2026-05-11T09:52:30Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T09:52:30Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095230

- timestamp: 2026-05-11T09:52:30Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T09:52:30Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095230

- timestamp: 2026-05-11T09:52:30Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T09:52:30Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095230

- timestamp: 2026-05-11T09:52:30Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T09:52:30Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095459

- timestamp: 2026-05-11T09:54:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T09:54:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095459

- timestamp: 2026-05-11T09:54:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T09:54:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095459

- timestamp: 2026-05-11T09:54:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T09:54:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095459

- timestamp: 2026-05-11T09:54:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T09:54:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095615

- timestamp: 2026-05-11T09:56:15Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T09:56:15Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095615

- timestamp: 2026-05-11T09:56:15Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T09:56:15Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095615

- timestamp: 2026-05-11T09:56:15Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T09:56:15Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-095615

- timestamp: 2026-05-11T09:56:15Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T09:56:15Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102621

- timestamp: 2026-05-11T10:26:21Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T10:26:21Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102621

- timestamp: 2026-05-11T10:26:21Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T10:26:21Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102621

- timestamp: 2026-05-11T10:26:21Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T10:26:21Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102621

- timestamp: 2026-05-11T10:26:21Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T10:26:21Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102748

- timestamp: 2026-05-11T10:27:48Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T10:27:48Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102748

- timestamp: 2026-05-11T10:27:48Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T10:27:48Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102748

- timestamp: 2026-05-11T10:27:48Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T10:27:48Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102748

- timestamp: 2026-05-11T10:27:48Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T10:27:48Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102920

- timestamp: 2026-05-11T10:29:20Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T10:29:20Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102920

- timestamp: 2026-05-11T10:29:20Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T10:29:20Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102920

- timestamp: 2026-05-11T10:29:20Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T10:29:20Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-102920

- timestamp: 2026-05-11T10:29:20Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T10:29:20Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-103636

- timestamp: 2026-05-11T10:36:36Z
- mode: ANY
- event_type: manual_pause
- triggered_by: user
- details: FOLKSUSDT naked entry: router reported algo_ids 3000001506912071/3000001506912106 but exchange has 0 open orders. Bracket-fix regression. Manual SL+TP being placed now.
- positions_affected: []
- action_taken: trading paused
- duration_minutes: 0
- resolved_at: 
- resolution_notes: run_safety_reset --pause

## SAFETY-20260511-103734

- timestamp: 2026-05-11T10:37:34Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T10:37:34Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-105806

- timestamp: 2026-05-11T10:58:06Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T10:58:06Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-105806

- timestamp: 2026-05-11T10:58:06Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T10:58:06Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-105806

- timestamp: 2026-05-11T10:58:06Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T10:58:06Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-105806

- timestamp: 2026-05-11T10:58:06Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T10:58:06Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-105859

- timestamp: 2026-05-11T10:58:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T10:58:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-105859

- timestamp: 2026-05-11T10:58:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T10:58:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-105859

- timestamp: 2026-05-11T10:58:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T10:58:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-105859

- timestamp: 2026-05-11T10:58:59Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T10:58:59Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-110220

- timestamp: 2026-05-11T11:02:20Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T11:02:20Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-110220

- timestamp: 2026-05-11T11:02:20Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T11:02:20Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-110220

- timestamp: 2026-05-11T11:02:20Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T11:02:20Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-110220

- timestamp: 2026-05-11T11:02:20Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T11:02:20Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-110322

- timestamp: 2026-05-11T11:03:22Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T11:03:22Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-110322

- timestamp: 2026-05-11T11:03:22Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T11:03:22Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-110322

- timestamp: 2026-05-11T11:03:22Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T11:03:22Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-110322

- timestamp: 2026-05-11T11:03:22Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T11:03:22Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-113802

- timestamp: 2026-05-11T11:38:02Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T11:38:02Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-113802

- timestamp: 2026-05-11T11:38:02Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T11:38:02Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-113802

- timestamp: 2026-05-11T11:38:02Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T11:38:02Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-113802

- timestamp: 2026-05-11T11:38:02Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T11:38:02Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-114139

- timestamp: 2026-05-11T11:41:39Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T11:41:39Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-114139

- timestamp: 2026-05-11T11:41:39Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T11:41:39Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-114139

- timestamp: 2026-05-11T11:41:39Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T11:41:39Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-114139

- timestamp: 2026-05-11T11:41:39Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T11:41:39Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-114238

- timestamp: 2026-05-11T11:42:38Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T11:42:38Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-114238

- timestamp: 2026-05-11T11:42:38Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T11:42:38Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-114238

- timestamp: 2026-05-11T11:42:38Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T11:42:38Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-114238

- timestamp: 2026-05-11T11:42:38Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T11:42:38Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-151802

- timestamp: 2026-05-11T15:18:02Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T15:18:02Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-162652

- timestamp: 2026-05-11T16:26:52Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T16:26:52Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-162728

- timestamp: 2026-05-11T16:27:28Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T16:27:28Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-164629

- timestamp: 2026-05-11T16:46:29Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T16:46:29Z
- resolution_notes: run_safety_reset --resume

## SAFETY-NAKED-20260511-164652-BILLUSDT

- timestamp: 2026-05-11T16:46:52Z
- mode: LIVE
- event_type: naked_entry_rescue
- triggered_by: execution-router
- details: symbol=BILLUSDT side=LONG proposal_id=PROP-20260511-BILLUSDT-001 entry_order_id=138036788 filled_qty=63; TP placement failed: BinanceAPIError: HTTP 400 code=-4116 msg='ClientOrderId is duplicated.' url=https://fapi.binance.com/fapi/v1/algoOrder?algoType=CONDITIONAL&clientAlgoId=TP-PROP-20260511-BILLUSDT-001&positionSide=BOTH&priceProtect=true&quantity=63&recvWindow=5000&reduceOnly=true&side=SELL&symbol=BILLUSDT&timeInForce=GTC&timestamp=1778518011695&triggerPrice=0.14917&type=TAKE_PROFIT_MARKET&workingType=MARK_PRICE&signature=<redacted>
- positions_affected: [PROP-20260511-BILLUSDT-001]
- action_taken: reduce-only MARKET close issued (close_order_id=138037016) — close succeeded
- duration_minutes: 0
- resolved_at: 2026-05-11T16:46:52Z
- resolution_notes: safety paused (carry_over_rollover=true); operator must verify exchange flat before resume

## SAFETY-20260511-164736

- timestamp: 2026-05-11T16:47:36Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T16:47:36Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-170907

- timestamp: 2026-05-11T17:09:07Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T17:09:07Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-180128

- timestamp: 2026-05-11T18:01:28Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T18:01:28Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-180908

- timestamp: 2026-05-11T18:09:08Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T18:09:08Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-181540

- timestamp: 2026-05-11T18:15:40Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T18:15:40Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-181540

- timestamp: 2026-05-11T18:15:40Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T18:15:40Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-181540

- timestamp: 2026-05-11T18:15:40Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T18:15:40Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-181540

- timestamp: 2026-05-11T18:15:40Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T18:15:40Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-181624

- timestamp: 2026-05-11T18:16:24Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T18:16:24Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-181624

- timestamp: 2026-05-11T18:16:24Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T18:16:24Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-181624

- timestamp: 2026-05-11T18:16:24Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T18:16:24Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-181624

- timestamp: 2026-05-11T18:16:24Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T18:16:24Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-183747

- timestamp: 2026-05-11T18:37:47Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T18:37:47Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-190926

- timestamp: 2026-05-11T19:09:26Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T19:09:26Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-193925

- timestamp: 2026-05-11T19:39:25Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T19:39:25Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-193925

- timestamp: 2026-05-11T19:39:25Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T19:39:25Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-193925

- timestamp: 2026-05-11T19:39:25Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T19:39:25Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-193925

- timestamp: 2026-05-11T19:39:25Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T19:39:25Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-194004

- timestamp: 2026-05-11T19:40:04Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: []
- action_taken: no open positions — emergency close was a no-op
- duration_minutes: 0
- resolved_at: 2026-05-11T19:40:04Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-194004

- timestamp: 2026-05-11T19:40:04Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 2/2; residual 0
- duration_minutes: 0
- resolved_at: 2026-05-11T19:40:04Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-194004

- timestamp: 2026-05-11T19:40:04Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [DOGEUSDT, SHIBUSDT]
- action_taken: closed 1/2; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T19:40:04Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-194004

- timestamp: 2026-05-11T19:40:04Z
- mode: LIVE
- event_type: emergency_exit
- triggered_by: safety-agent
- details: manual emergency
- positions_affected: [MYSTERYUSDT]
- action_taken: closed 0/1; residual 1
- duration_minutes: 0
- resolved_at: 2026-05-11T19:40:04Z
- resolution_notes: emergency_close_all completed

## SAFETY-20260511-194529

- timestamp: 2026-05-11T19:45:29Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T19:45:29Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-195457

- timestamp: 2026-05-11T19:54:57Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T19:54:57Z
- resolution_notes: run_safety_reset --resume

## SAFETY-20260511-200503

- timestamp: 2026-05-11T20:05:03Z
- mode: ANY
- event_type: manual_resume
- triggered_by: user
- details: no reason given
- positions_affected: []
- action_taken: trading paused flag cleared
- duration_minutes: 0
- resolved_at: 2026-05-11T20:05:03Z
- resolution_notes: run_safety_reset --resume
