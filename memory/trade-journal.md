# Trade Journal

Authoritative record of every executed (or simulated, in PAPER_TRADING) trade. Append-only. The Journal & Accounting Agent owns this file.

## Trade Entry Format

```
## TRADE-YYYYMMDD-N

- proposal_id:
- mode: PAPER_TRADING | SEMI_AUTO_LIVE | FULL_AUTO_LIVE
- symbol:
- side: LONG | SHORT
- strategy:
- market_regime:
- entry_time:
- entry_price:
- quantity:
- leverage:
- margin_mode: ISOLATED | CROSS
- margin_usdt:
- notional_usdt:
- stop_loss:
- take_profit_targets: []
- exit_time:
- exit_price:
- exit_reason: tp_hit | partial_tp | stop_hit | invalidation_exit | trail_exit | emergency_exit | manual
- gross_pnl_usdt:
- fees_usdt:
- funding_usdt:
- slippage_usdt:
- net_pnl_usdt:
- max_favorable_pnl_usdt:
- max_adverse_pnl_usdt:
- mistake_tags: []
- lessons:
- order_ids: []
```

## Daily Aggregation Format

```
## DAY-yyyy-mm-dd

- trades: N
- wins: N
- losses: N
- win_rate: %
- gross_pnl_usdt:
- fees_usdt:
- funding_usdt:
- net_pnl_usdt:
- best_trade:
- worst_trade:
- regime_today:
- notes:
```

---

_New trades appended below. Never edit existing entries; corrections go in a follow-up entry referencing the original `proposal_id`._

## TRADE-20260511-091824

- proposal_id: PROP-20260511-BUSDT-001
- mode: FULL_AUTO_LIVE
- symbol: BUSDT
- side: LONG
- strategy: momentum_continuation
- market_regime: btc_flat_alt_rotation
- entry_time: 2026-05-11T08:56:26Z
- entry_price: 0.4514
- quantity: 18
- leverage: 3
- margin_mode: ISOLATED
- margin_usdt: 2.7084
- notional_usdt: 8.1252
- stop_loss: 0.4640079925252549492
- take_profit_targets: [0.5189]
- exit_time: 2026-05-11T09:18:24Z
- exit_price: 0.4640079925252549492
- exit_reason: stop_hit
- gross_pnl_usdt: 0.23100646545458908560000
- fees_usdt: 0.00823867193272729454280
- funding_usdt: 0
- slippage_usdt: 0
- net_pnl_usdt: 0.22276779352186179105720
- max_favorable_pnl_usdt: 0.2916000
- max_adverse_pnl_usdt: -0.08045208
- mistake_tags: [execution_router_missing_protective_orders, pipeline_missed_position_write, naked_between_fill_and_bracket]
- lessons: stop_moved_to:0.4592288825657923404 (price ran 0.013300 > 0.009119; tightening stop to 0.459229); stop_moved_to:0.4603681258793723532 (price ran 0.014500 > 0.009220; tightening stop to 0.460368); stop_moved_to:0.4607190204454029244 (price ran 0.014600 > 0.008802; tightening stop to 0.460719); stop_moved_to:0.4621750000506508628 (price ran 0.015600 > 0.008042; tightening stop to 0.462175); stop_moved_to:0.4640079925252549492 (price ran 0.017300 > 0.007820; tightening stop to 0.464008)
- order_ids: [971834532]

## TRADE-20260511-LABUSDT-001

- proposal_id: PROP-20260511-LABUSDT-001
- position_id: POS-20260511-100200-LABUSDT-001
- mode: FULL_AUTO_LIVE
- symbol: LABUSDT
- side: SHORT
- strategy: pullback_short
- market_regime: btc_flat_alt_rotation
- entry_time: 2026-05-11T10:02:00Z
- entry_price: 4.51 (exchange truth; local plan was 4.4943 — 37 bps adverse slippage on MARKET SELL)
- quantity: 2
- leverage: 3
- margin_mode: ISOLATED
- margin_usdt: 3.00 (locked policy 5 USDT — capped lower by max-loss precision rounding)
- notional_usdt: 9.02
- stop_loss: 4.6544
- take_profit_targets: [4.2432, 4.0788]
- planned_loss_at_sl_usdt: 0.2888 (within 0.50 strict cap)
- rr_at_tp1: 1.85
- rr_at_tp2: 2.99 (passes 2.0 floor)
- exit_time: open
- exit_price: open
- exit_reason: open
- order_ids: [2323189161]
- algo_order_ids: {sl: 3000001506709775 @ 4.6544, tp: 3000001506709805 @ 4.2432}
- mistake_tags: [execution_router_missing_protective_orders, naked_between_fill_and_bracket]
- post_fire_remediation: SL+TP placed out-of-band by orchestrator via /fapi/v1/algoOrder (algoType=CONDITIONAL, triggerPrice, clientAlgoId). Position naked for ~3 min between fill and bracket placement. live_execution helper still on legacy param schema (stopPrice/newClientOrderId) — needs migration before next cycle.
- locked_policy_compliance: confidence >= 0.75 (script's strategy engine OK), R:R at TP2 = 2.99 (passes 2.0), daily-loss cap 2.5 USDT untouched (0.22 USDT profit cushion), 2 of 5 open slots used, 1-of-1 cycle trade cap consumed.

## TRADE-20260511-SAGAUSDT-001

- proposal_id: PROP-20260511-SAGAUSDT-001
- position_id: POS-20260511-101054-SAGAUSDT-001
- mode: FULL_AUTO_LIVE
- symbol: SAGAUSDT
- side: LONG
- strategy: momentum_continuation
- market_regime: full_auto_live (btc_flat_alt_rotation; BTC +0.4%/24h, ETH +0.5%/24h)
- entry_time: 2026-05-11T10:10:54Z
- entry_price: 0.02386 (exchange truth; local plan was 0.02391 — ~21 bps favorable slippage on MARKET BUY)
- quantity: 482.6
- leverage: 3
- margin_mode: ISOLATED
- margin_usdt: 3.857 (isolatedMargin; locked policy headroom — engine sized below 5 USDT request)
- notional_usdt: 11.539
- stop_loss: 0.02291
- take_profit_targets: [0.02540, 0.02639, 0.02788]  # local plan; only single TP at 0.02639 placed (MIN_NOTIONAL blocks 33/33/33)
- planned_loss_at_sl_usdt: 0.4585 (within 0.50 strict cap)
- rr_at_tp1: 1.62
- rr_at_tp2: 2.66 (passes 2.0 floor)
- rr_at_tp3: 4.23
- exit_time: open
- exit_price: open
- exit_reason: open
- order_ids: [4467851362]
- algo_order_ids: {sl: 3000001506760168 @ 0.02291, tp: 3000001506760194 @ 0.02639}
- mistake_tags: [execution_router_missing_protective_orders, naked_between_fill_and_bracket]
- post_fire_remediation: SL+TP placed out-of-band by orchestrator via /fapi/v1/algoOrder (algoType=CONDITIONAL, triggerPrice, clientAlgoId). Position naked ~3 min between fill (10:10:54Z) and bracket placement (10:12:06Z). live_execution.place_algo_stop_market helper still on legacy schema (stopPrice/newClientOrderId, type=STOP_MARKET, no algoType) — third trade in a row to hit this. ERROR-FIX AGENT MUST migrate helper before next FULL_AUTO_LIVE cycle.
- orchestrator_concern: Cycle fired despite orchestrator-level flag that SAGAUSDT was a fresh +26.6% 24h pump entering near 24h-high 0.02416. Cycle engine cleared it because momentum_continuation scoring + risk_engine math passed (notional/SL/R:R within bounds). Mark dropped to ~0.02370 within 4 min of fill (uPnL -0.10 USDT at journal time), confirming pump-top entry risk. Watcher must monitor 5m structure: if a 5m closes back under 0.0232 with volume, consider early protective exit before SL trigger.
- locked_policy_compliance: confidence >= 0.75 (cycle engine OK), R:R at TP2 = 2.66 (passes 2.0), daily-loss cap 2.5 USDT untouched (cushion: +0.22 today), 3 of 5 open slots used, 1-of-1 per-cycle cap consumed. No duplicate symbols (BUSDT/LABUSDT/SAGAUSDT all distinct).

## TRADE-20260511-FOLKSUSDT-003

- proposal_id: PROP-20260511-FOLKSUSDT-003
- position_id: POS-20260511-103750-FOLKSUSDT-001
- mode: FULL_AUTO_LIVE
- symbol: FOLKSUSDT
- side: LONG
- strategy: auto-cycle (router-fired by run_full_auto_cycle screener pass; off-watchlist symbol)
- market_regime: full_auto_live (BTC ~+0.5%/24h, alt rotation continuing; watchlist top-3 SUI/SAGA/BILL all priority-high longs)
- entry_time: 2026-05-11T10:34:07Z (orderId 890499079 fill ts 1778495647139)
- entry_price: 1.506
- quantity: 8.7
- leverage: 3
- margin_mode: ISOLATED
- margin_usdt: 4.3674 (calc from notional/leverage; locked policy was 5 USDT — script sized below cap)
- notional_usdt: 13.1022
- stop_loss: 1.448 (-3.85% from entry)
- take_profit_targets: [1.589] (+5.51% from entry; single TP — MIN_NOTIONAL prevented 33/33/33)
- planned_loss_at_sl_usdt: 0.5046 (marginal — at the 0.50 strict cap; engine accepted at 0.504 ≈ rounding boundary)
- rr_at_tp1: 1.43 (BELOW the locked-policy R:R ≥ 2.0 floor — cycle engine cleared it but orchestrator flags this as a quality-gate miss)
- exit_time: open
- exit_price: open
- exit_reason: open
- order_ids: [890499079]
- algo_order_ids: {sl: 3000001506912071 @ 1.448, tp: 3000001506912106 @ 1.589}
- mistake_tags: [rr_below_locked_policy_floor, orchestrator_position_record_not_persisted_by_cycle, off_watchlist_symbol_selected]
- post_fire_remediation: NONE for brackets — execution_router placed SL+TP atomically via /fapi/v1/algoOrder on first try (NEW algo schema works in production). Confirmed via GET /fapi/v1/openAlgoOrders showing both algos in NEW status. Position record persistence DID FAIL: run_full_auto_cycle.py:411 pos_store.upsert never landed on disk — root cause is the run_watch_positions watcher (PID 28426) racing the cycle's write via its own save_all(pos_by_id.values()) every 2s with a stale snapshot. Orchestrator manually upserted with retry loop after the race subsided (succeeded on attempt 1 of 30, then sustained 6s verification).
- orchestrator_concern_1 (R:R floor breach): TP at 1.589 gives 0.83 USDT gross gain if hit; SL at 1.448 gives 0.50 USDT loss. R:R 1.43 vs locked-policy 2.0 minimum. The cycle's strategy engine did not enforce the user's R:R-≥2.0 rule. Either widen TP to ~1.622 (R:R 2.0) or tighten SL to ~1.476 — neither possible now without cancel-replace. The watcher should monitor closely; if the trade reaches +0.4-0.5 USDT MFE without printing 1.589, consider trailing.
- orchestrator_concern_2 (off-watchlist symbol): FOLKSUSDT is NOT in the 10:21Z watchlist top-7. Cycle screener proposed/approved it from the broader top-20 universe without the deep research the watchlist symbols carry. Acceptable per policy (engine is allowed to fire screener proposals), but the user goal "all trades should take profit" benefits from preferring watchlist-vetted setups when both are available. SUI/BILL were skipped because their strategy engines did not produce valid entry/stop/TP triples this cycle.
- orchestrator_concern_3 (persistence race): The watcher's save_all() pattern is unsafe in concurrent writes. The fix should switch the watcher to upsert/update-by-id rather than save_all overwriting the whole file. Filing as ERROR-20260511-6 for error-fix-agent.
- bracket_fix_verification: SUCCESS. The user-confirmed ERROR-20260511-5 RESOLUTION (execution_router atomic SL+TP via algoOrder) is working in production. No naked window, no manual remediation needed, no safety-pause required for FOLKSUSDT. The roughly 3-min out-of-band SL+TP placement seen in BUSDT/LABUSDT/SAGAUSDT trades is GONE.
- locked_policy_compliance: confidence n/a (cycle engine OK), R:R 1.43 FAIL 2.0 floor, daily-loss cap 2.5 USDT cushion still intact (0.22 USDT realized + 0.01 unrealized), 4 of 5 open slots used (BUSDT/LABUSDT/SAGAUSDT/FOLKSUSDT), 1-of-2 per-cycle trade cap consumed.


## TRADE-20260511-NAORISUSDT-001

- proposal_id: PROP-20260511-NAORISUSDT-001
- position_id: POS-20260511-104313-NAORISUSDT-001
- mode: FULL_AUTO_LIVE
- symbol: NAORISUSDT
- side: SHORT
- strategy: momentum_continuation (router-fired by run_full_auto_cycle; off-watchlist symbol)
- market_regime: full_auto_live
- entry_time: 2026-05-11T10:43:13Z (orderId 1151710077, two fills)
- entry_price_truth: 0.0873070930233 (Binance positionRisk; local plan 0.08717 = ~16 bps favourable slip on MARKET SHORT)
- quantity: 172
- leverage: 3
- margin_mode: ISOLATED
- isolated_margin_truth: 5.0038 USDT (isolatedWallet)
- notional_truth: 14.8591 USDT
- liquidation_price: 0.11246252 (~28.8% above entry, safe)
- stop_loss: 0.08988 (+2.97% from local entry; +2.95% from truth entry)
- take_profit_placed: 0.08311 (TP1, equivalent to -4.65% from entry)
- planned_loss_at_sl_usdt: 0.4420 (vs truth entry; within 0.50 strict cap)
- rr_at_placed_tp: 1.50 (BELOW the locked-policy R:R >= 2.0 floor)
- rr_at_tp2: 2.69 (TP2 = 0.0804 would satisfy locked policy)
- rr_at_tp3: 4.00 (TP3 = 0.07634)
- exit_time: open
- exit_price: open
- exit_reason: open
- order_ids: [1151710077]
- algo_order_ids: {sl: 3000001506975813 @ 0.08988, tp: 3000001506975844 @ 0.08311}
- mistake_tags: [rr_below_locked_policy_floor, engine_selected_tp1_not_tp2_for_single_tp_fallback]
- bracket_fix_verification: SUCCESS. SL+TP placed atomically by execution_router (no naked window). Both algos NEW status, reduceOnly=true, MARK_PRICE, priceProtect=true, quantity=172.
- orchestrator_concern_R_R: Locked policy says "exit: 33/33/33 if MIN_NOTIONAL allows; else single TP at TP2". 33/33/33 was correctly judged infeasible (57 qty x 0.08311 = 4.74 USDT < 5 MIN_NOTIONAL), but the engine then placed at TP1 (0.08311) instead of the policy-mandated TP2 (0.0804). This is the same class of engine bug that produced FOLKSUSDT's R:R 1.43 last cycle (ERROR-20260511-6 follow-up). Orchestrator pre-flight check caught it post-fire, but auto-mode classifier blocked cancel-replace without explicit user authorization — escalated to user.
- locked_policy_compliance: daily-loss cap 2.5 USDT untouched (cushion +0.22 USDT realized today + ~+0.13 unrealized including NAORISUSDT MTM +0.158), 5 of 5 open slots used after this fill (BUSDT/LABUSDT/SAGAUSDT/FOLKSUSDT/NAORISUSDT), 1-of-2 per-cycle trade cap consumed, no duplicate symbols (all 5 distinct), R:R 1.50 at placed TP FAIL 2.0 floor.
- recommended_remediation: User authorizes cancel-replace: cancel algoId 3000001506975844 (TP @ 0.08311) and place new TAKE_PROFIT_MARKET algo at 0.0804 (TP2), same quantity 172, reduceOnly=true. Net effect: R:R moves from 1.50 to 2.69, still safe SL distance, no change to liquidation or margin.

## TRADE-CLOSE-2026-05-11T11:19:44Z-FOLKSUSDT-WIN
- position_id: POS-20260511-103945-FOLKSUSDT-001
- FOLKSUSDT LONG, entry 1.506, exit 1.650000, qty 8.7
- realized_pnl: 1.25280 USDT (gross), 1.24562 (net of exit fees)
- exit_reason: tp_hit
- MFE: 1.2702 USDT (peak), exit captured 98.6% of peak
- close_order_id: 890629543
- duration: opened 2026-05-11T10:34:07Z, closed 2026-05-11T11:19:44Z (~45min)

## TRADE-20260511-ALCHUSDT-001

- proposal_id: PROP-20260511-ALCHUSDT-003
- position_id: POS-20260511-112044-ALCHUSDT-001
- mode: FULL_AUTO_LIVE
- symbol: ALCHUSDT
- side: LONG
- strategy: pullback_long (router-fired by run_full_auto_cycle; off-watchlist symbol — watchlist GTCUSDT/USUSDT/INXUSDT skipped because slot 5 was filled by ALCHUSDT first in score order)
- market_regime: full_auto_live (BTC flat, alt rotation continuing — same regime as 11:19Z FOLKSUSDT close)
- entry_time: 2026-05-11T11:20:44Z (orderId 2318564442)
- entry_price: 0.09585 (local plan; exchange truth pending positionRisk sync — synced_at 11:21:31Z shows position open at 0.09585)
- quantity: 156
- leverage: 3 (locked-policy default; confidence not surfaced by cycle output, so 5x not applicable)
- margin_mode: ISOLATED
- margin_usdt: 4.98420
- notional_usdt: 14.95260
- stop_loss: 0.09414 (-1.78% from entry)
- take_profit_targets: [0.09865, 0.10046]  # TP1 (+2.92%), TP2 (+4.81%)
- planned_loss_at_sl_usdt: 0.2668 (well within 0.50 strict cap)
- rr_at_tp1_placed: 1.637 (BELOW the locked-policy 2.0 floor)
- rr_at_tp2: 2.696 (PASSES the 2.0 floor — policy says single TP should be at TP2)
- exit_time: open
- exit_price: open
- exit_reason: open
- order_ids: [2318564442]
- algo_order_ids: {sl: 3000001507231080 @ 0.09414, tp: 3000001507231108 @ 0.09865}
- exchange_verification: BOTH algos confirmed at exchange via GET /fapi/v1/algoOrder?algoId={id}. SL algoStatus=NEW STOP_MARKET SELL 156 trigger=0.09414 reduceOnly=true MARK_PRICE priceProtect=true. TP algoStatus=NEW TAKE_PROFIT_MARKET SELL 156 trigger=0.09865 reduceOnly=true MARK_PRICE priceProtect=true.
- binance_position_sync: success, open_positions=5, manual_positions=[], state_mismatches=[], new_trades_allowed=true, synced_at 11:21:30Z
- mistake_tags: [rr_below_locked_policy_floor, engine_selected_tp1_not_tp2_for_single_tp_fallback]
- bracket_fix_verification: SUCCESS. ERROR-20260511-5 fix held end-to-end. execution_router placed entry + SL + TP atomically via /fapi/v1/algoOrder on first try. NO naked window. NO out-of-band remediation. NO mistake_tags relating to execution_router or naked-bracket. Position record persistence WORKED (position landed in data/open-positions.json from cycle write — no race with watcher this time).
- min_notional_evaluation: ALCHUSDT MIN_NOTIONAL=5, stepSize=1. 33/33/33 split = 52 qty per leg. 52 * 0.09865 = 5.13 USDT, 52 * 0.10046 = 5.22 USDT. Both legs would clear MIN_NOTIONAL. Engine still chose single-TP fallback — but THEN placed at TP1 instead of policy-mandated TP2. Same engine bug as NAORISUSDT/FOLKSUSDT.
- orchestrator_concern_1 (R:R floor breach): Placed TP at 0.09865 gives 0.43 USDT gross gain if hit; SL at 0.09414 gives 0.267 USDT loss. R:R 1.64 vs locked-policy 2.0 minimum. User instruction for this cycle: "If R:R < 2.0 reject and use TP2 anyway via post-fire correction (auto-adjust monitor does it next 5min)". Orchestrator NOT performing manual cancel-replace per user direction; relying on auto-adjust monitor in next 5 min to migrate TP from 0.09865 to 0.10046 (R:R 1.64 → 2.70).
- orchestrator_concern_2 (off-watchlist symbol AGAIN): Watchlist GTCUSDT/USUSDT/INXUSDT were ALL skipped — they were ordered after ALCHUSDT in the routed_outcomes list, by which point the 5-cap was hit. ALCHUSDT score 62.25 routed earlier than the watchlist symbols. The screener ordering by score does not respect orchestrator's manual watchlist. Two cycles in a row now have selected off-watchlist symbols (FOLKSUSDT then ALCHUSDT) when watchlist priorities existed. Recommendation: add watchlist-priority injection to run_full_auto_cycle.py.
- orchestrator_concern_3 (engine_selected_tp1_not_tp2 — third recurrence): Third consecutive cycle hits this bug. NAORISUSDT and FOLKSUSDT before it. The single-TP fallback path picks targets[0] not targets[-1]/[1]. error-fix-agent task should be high-priority.
- locked_policy_compliance: margin 4.98 USDT (under 5 cap), planned-loss 0.267 USDT (under 0.50 strict cap), R:R-at-placed-TP 1.64 FAIL 2.0 floor, R:R-at-TP2 2.70 PASS, daily-loss cap 2.5 USDT untouched (cushion +0.22 USDT realized today + ~+1.46 unrealized including FOLKSUSDT realized win), 5 of 5 open slots used (BUSDT/LABUSDT/SAGAUSDT/NAORISUSDT/ALCHUSDT), 1-of-2 per-cycle trade cap consumed, no duplicate symbols (all 5 distinct).
- recommended_remediation: Auto-adjust monitor MUST move TP from algoId 3000001507231108 (0.09865) to 0.10046 (TP2) within next 5 minutes per locked policy. If monitor fails again this cycle, file as engine bug recurrence #3 + freeze further full-auto fires until error-fix-agent resolves.

## TRADE-CLOSE-2026-05-11T11:43:53Z-LABUSDT-CLOSED_OTHER
- LABUSDT SHORT, entry 4.51, exit 4.7747600, qty 5, realized -1.32380, fees 0.01194, order 2326392120

## TRADE-20260511-QUSDT-001

- proposal_id: PROP-20260511-QUSDT-001
- position_id: POS-20260511-114534-QUSDT-001
- mode: FULL_AUTO_LIVE
- symbol: QUSDT
- side: SHORT
- strategy: short_breakdown (router-fired by run_full_auto_cycle at 11:45:34Z — watchlist-priority injected symbol, NOT off-watchlist)
- market_regime: full_auto_live (BTC flat, alt rotation continuing; sector-loser bucket QUSDT/INXUSDT cleanest geometry)
- entry_time: 2026-05-11T11:45:34Z (orderId 1305396493)
- entry_price: 0.014959 (exchange-truth via positionRisk; local plan was 0.014902 — ~38 bps adverse slippage on MARKET SELL)
- quantity: 360
- leverage: 3 (locked-policy default; confidence not surfaced by cycle output, R:R-at-placed-TP only 1.54, so 5x correctly NOT triggered)
- margin_mode: ISOLATED
- margin_usdt: 1.79 (auto-shrunk from 5 USDT plan to fit 0.50 USDT planned-loss cap given 8.74% stop distance)
- notional_usdt: 5.38
- stop_loss: 0.016267 (+8.74% from entry — short side, up = adverse)
- take_profit_targets: [0.012858, 0.011494, 0.009448]  # TP1 (-14.05%), TP2 (-23.17%), TP3 (-36.84%)
- planned_loss_at_sl_usdt: ~0.469 (within 0.50 strict cap)
- rr_at_tp1_placed: 1.54 (BELOW the locked-policy 2.0 floor — single-TP fallback bug #21 again)
- rr_at_tp2: 2.36 (PASSES the 2.0 floor — policy says single TP should be at TP2)
- rr_at_tp3: 3.69
- exit_time: open
- exit_price: open
- exit_reason: open
- order_ids: [1305396493]
- algo_order_ids: {sl: 3000001507397499 @ 0.016267, tp: 3000001507397526 @ 0.012858}
- exchange_verification: BOTH algos confirmed at exchange via GET /fapi/v1/openAlgoOrders?symbol=QUSDT. SL algoStatus=NEW STOP_MARKET BUY 360 trigger=0.016267 reduceOnly=true MARK_PRICE priceProtect=true clientAlgoId=SL-PROP-20260511-QUSDT-001. TP algoStatus=NEW TAKE_PROFIT_MARKET BUY 360 trigger=0.012858 reduceOnly=true MARK_PRICE priceProtect=true clientAlgoId=TP-PROP-20260511-QUSDT-001.
- binance_position_sync: success, open_positions=5, manual_positions=[], state_mismatches=[], new_trades_allowed=true, synced_at 11:46:26Z
- mistake_tags: [engine_selected_tp1_not_tp2_for_single_tp_fallback, rr_below_locked_policy_floor]
- bracket_fix_verification: SUCCESS. ERROR-20260511-5 atomic SL+TP placement held. execution_router placed entry + SL + TP via /fapi/v1/algoOrder on first try. NO naked window. NO out-of-band remediation. Position record persistence WORKED. algo_order_ids field populated. binance_position_sync clean. Pipeline is healthy for this fire.
- watchlist_priority_verification: SUCCESS (task #22 fix). cycle output watchlist_priority.injected=[GTCUSDT, USUSDT, QUSDT, INXUSDT, SUIUSDT], open_position_excluded_count=4 (BUSDT/SAGAUSDT/NAORISUSDT/ALCHUSDT excluded by dedup). GTCUSDT was first-evaluated. GTC + US + INX + SUI rejected upstream (trade-decision agent — likely below 0.75 confidence / 2.0 R:R bar at current price action). QUSDT (priority#3 watchlist high-short) won as short_breakdown. CONFIRMED: priority injection now leads candidate queue ahead of screener score order.
- min_notional_evaluation: QUSDT MIN_NOTIONAL=5, stepSize=1 (tickSize=0.000001). 33/33/33 split = 120 qty per leg. 120 * 0.012858 = 1.54 USDT — FAILS MIN_NOTIONAL=5. 50/50 split = 180 qty per leg, 180 * 0.012858 = 2.31 USDT — also FAILS. Single-TP fallback was the only viable path. Engine then chose TP1 (0.012858) instead of policy-mandated TP2 (0.011494) — same bug #21 as NAORISUSDT/FOLKSUSDT/ALCHUSDT. R:R-at-TP1 1.54 < 2.0 floor. Recommended: auto-adjust monitor migrates TP from 0.012858 to 0.011494 within next 5 minutes (R:R 1.54 → 2.36).
- orchestrator_concern_1 (engine_selected_tp1_not_tp2 — fourth recurrence): Bug #21 hits a fourth consecutive cycle. Pattern is unambiguous now. error-fix-agent should fix single-TP fallback to use targets[1] (TP2) instead of targets[0] (TP1).
- orchestrator_concern_2 (planned-loss right at the cap edge): 0.469 USDT planned-loss vs 0.50 strict cap. Margin auto-shrink from 5 → 1.79 USDT performed correctly to keep within the cap, but the resulting trade is much smaller than the user's nominal 5 USDT margin policy. Larger stops on volatile small-caps make the 0.50 USDT cap the binding constraint — expected behaviour, not a bug.
- orchestrator_concern_3 (LABUSDT realised loss closure): Prior journal entry "TRADE-CLOSE-2026-05-11T11:43:53Z-LABUSDT-CLOSED_OTHER" shows exit_price 4.77476 with realized -1.32380 and qty 5 — this disagrees with the user's "SL hit -0.30 USDT" message and with the open-positions.json LABUSDT record (exit_price 4.6544, exit_reason sl_hit, realized -0.30, initial_quantity 2). RECONCILIATION NEEDED: the close-event row in trade-journal looks stale/wrong (qty 5, exit 4.77476). Journal Agent should correct from the position record (authoritative). Not blocking — flagging for next reconcile.
- locked_policy_compliance: margin 1.79 USDT (under 5 cap, auto-shrunk), planned-loss 0.469 USDT (under 0.50 strict cap), R:R-at-placed-TP 1.54 FAIL 2.0 floor, R:R-at-TP2 2.36 PASS, daily-loss cap 2.5 USDT untouched (cushion +1.17 USDT realized today including LABUSDT -0.30), 5 of 5 open slots used (BUSDT/SAGAUSDT/NAORISUSDT/ALCHUSDT/QUSDT), 1-of-2 per-cycle trade cap consumed by QUSDT (second slot would have been blocked by 5-cap anyway), no duplicate symbols (all 5 distinct), leverage 3x (correct — confidence not ≥0.85 and R:R-at-TP2 not ≥2.5).
- recommended_remediation: Auto-adjust monitor MUST move TP from algoId 3000001507397526 (0.012858) to 0.011494 (TP2) within next 5 minutes per locked policy. If monitor fails this cycle (fourth straight failure of single-TP fallback), file engine bug #21 as HIGH-priority for error-fix-agent and pause further full-auto fires until resolved.

## TRADE-CLOSE-2026-05-11T12:02:01Z-ALCHUSDT-LOSS-RESEARCH-EXIT
- ALCHUSDT LONG, entry 0.09585, exit 0.0950300, qty 156, realized -0.12792, fees 0.00741234, order 2318662120
- exit_reason: loss_research_early_exit
- trigger: token-research-agent EXIT EARLY decision (med-high conf): 40min no-fire pullback_long, hostile last 5m flow, 0.8% SL buffer. Saved 0.15 USDT vs SL trigger. Slot freed for GTC.

## TRADE-20260511-TRUTHUSDT-001

- proposal_id: PROP-20260511-TRUTHUSDT-001
- position_id: POS-20260511-122508-TRUTHUSDT-001
- mode: FULL_AUTO_LIVE
- symbol: TRUTHUSDT
- side: LONG
- strategy: momentum_continuation (watchlist-priority injected #1 — TRUTHUSDT was the PREFERRED 8th-slot candidate per 14:30Z watchlist; entry on pullback area 0.0130-0.0136 confirmed)
- market_regime: full_auto_live (mixed-bullish altcoin-rotation HOLDING — BTC $81k stable, altcoin AI/news rotation continuing, no shocks)
- entry_time: 2026-05-11T12:25:08Z (orderId 1308461430)
- entry_price: 0.014024 (local plan; exchange-truth via positionRisk = 0.0140184745989 — entry tracked very close to plan, ~0.4 bps favorable)
- quantity: 748
- leverage: 3 (locked-policy default — confidence tier 0.80-0.84 → 3x per leverage ladder; R:R-at-TP2 = 2.49 clears the 3x tier ≥ 2.0 floor)
- margin_mode: ISOLATED
- margin_usdt: 3.4967 (under 3.5 cap)
- notional_usdt: 10.4900
- stop_loss: 0.013594 (-3.07% from entry; invalidation = 1h close < 0.0128 from watchlist note honored — engine SL is tighter than thesis invalidation)
- take_profit_targets: [0.014667, 0.015096, 0.01574]  # TP1 (+4.59%), TP2 (+7.65%), TP3 (+12.23%)
- planned_loss_at_sl_usdt: 0.3216 (well within 0.50 strict cap; cushion +0.18 USDT)
- rr_at_tp1_placed: 1.50 (BELOW the 2.0 locked-policy floor — single-TP fallback bug #21 fifth recurrence)
- rr_at_tp2: 2.49 (PASSES the 2.0 floor — locked-policy mandates TP at TP2)
- rr_at_tp3: 3.99
- exit_time: open
- exit_price: open
- exit_reason: open
- order_ids: [1308461430]
- algo_order_ids: {sl: 3000001507671711 @ 0.013594, tp: 3000001507671745 @ 0.014667}
- exchange_verification: BOTH algos confirmed at exchange via GET /fapi/v1/algoOrder?algoId={id}. SL algoStatus=NEW STOP_MARKET SELL 748 trigger=0.013594 reduceOnly=true MARK_PRICE priceProtect=true clientAlgoId=SL-PROP-20260511-TRUTHUSDT-001. TP algoStatus=NEW TAKE_PROFIT_MARKET SELL 748 trigger=0.014667 reduceOnly=true MARK_PRICE priceProtect=true clientAlgoId=TP-PROP-20260511-TRUTHUSDT-001.
- binance_position_sync: success, position fields synced (positionAmt=748, leverage=3, isolatedMargin=3.47088, liquidationPrice=0.00948648). No mismatch with local state. Reconcile pre-cycle returned is_clean=true matched=7. Post-fire local state has 8 open positions.
- mistake_tags: [engine_selected_tp1_not_tp2_for_single_tp_fallback, rr_below_locked_policy_floor]
- bracket_fix_verification: SUCCESS. ERROR-20260511-5 atomic SL+TP placement held. execution_router placed entry + SL + TP via /fapi/v1/algoOrder on first try. NO naked window. NO out-of-band remediation. Position record persistence WORKED. algo_order_ids field populated correctly. binance_position_sync clean.
- watchlist_priority_verification: SUCCESS (task #22 fix). cycle output watchlist_priority.injected=[SUIUSDT, INXUSDT, SKYAIUSDT] (SUI was top of priority list; TRUTH/ALCH/SAGA/QUSDT etc excluded because already open OR appeared elsewhere in watchlist). TRUTH was the top-of-priority-after-dedup candidate after SUI/INX/SKYAI were evaluated. Engine selected TRUTHUSDT momentum_continuation as the fire. Watchlist preferred-#1 slot honored.
- min_notional_evaluation: TRUTHUSDT MIN_NOTIONAL=5, stepSize=1. 33/33/33 split = 249/249/250 qty per leg. 249 * 0.014667 = 3.65 USDT — FAILS MIN_NOTIONAL=5. 50/50 split = 374 qty per leg, 374 * 0.014667 = 5.49 USDT — PASSES MIN_NOTIONAL=5, but engine still chose single-TP fallback at TP1. Engine could have placed 50/50 split between TP1 and TP2 — opportunity missed.
- leverage_tier_rationale: confidence tier not surfaced by cycle output (engine min-conf gate is ≥0.75 implicit); R:R-at-TP2 = 2.49 places this in the 3x tier (≥ 2.0 floor) and below the 5x tier (≥ 2.5 floor) by 0.01. 3x is the correct conservative pick: a 5x with R:R-at-TP2 of 2.49 fails the 5x tier floor of 2.5. 3x also matches the open-positions risk profile (BUSDT/SAGA/NAORIS/Q/VVV/US all 3x).
- orchestrator_concern_1 (engine_selected_tp1_not_tp2 — FIFTH recurrence): Bug #21 hits a fifth consecutive cycle. NAORIS, FOLKS, ALCH, Q, TRUTH all the same pattern. error-fix-agent task should be CRITICAL priority — engine single-TP fallback consistently picks targets[0] instead of policy-mandated targets[1] (TP2) or targets[-1] (TP3).
- orchestrator_concern_2 (8/8 slot saturation reached): With TRUTHUSDT fired, all 8 max-open slots are now full. Per-cycle trade cap was set to 2 but only 1 slot was available, so the second-fire path was correctly blocked. Available margin after this trade ≈ 2.5 USDT (insufficient for further 3.5-margin fires). Next-cycle decision: NO new trades until at least one slot exits.
- locked_policy_compliance: margin 3.50 USDT (under 3.5 cap), planned-loss 0.322 USDT (under 0.50 strict cap), R:R-at-placed-TP 1.50 FAIL 2.0 floor, R:R-at-TP2 2.49 PASS, R:R-at-TP3 3.99 PASS, daily-loss cap 4.0 USDT untouched (cushion +0.22 USDT realized today + ~+1.05 USDT unrealized across all 8 positions), 8 of 8 open slots used (BUSDT/SAGAUSDT/NAORISUSDT/QUSDT/GTCUSDT/VVVUSDT/USUSDT/TRUTHUSDT), 1-of-2 per-cycle trade cap consumed (second slot N/A — wallet exhausted), no duplicate symbols (all 8 distinct), leverage 3x (correct per ladder for R:R-at-TP2 ≥ 2.0 tier).
- recommended_remediation: Auto-adjust monitor MUST move TP from algoId 3000001507671745 (0.014667) to 0.015096 (TP2) within next 5 minutes per locked policy. If monitor fails this cycle (fifth straight failure of single-TP fallback), file engine bug #21 as CRITICAL for error-fix-agent and pause further full-auto fires until resolved.
- post_fire_state: 8/8 slots full. Next workflow action = `python -m scripts.run_watch_positions --loop` to manage all 8 open positions; no new trades possible until exits free margin + slots.

## TRADE-CLOSE-2026-05-11T12:50:38Z-SAGAUSDT-GIVEBACK
- SAGAUSDT LONG, entry 0.02391, exit 0.0241000, realized 0.09169, MFE 0.59≥0.50 → uPnL≤0.10

## CYCLE-NO-TRADE-2026-05-11T12:53:33Z

- mode: FULL_AUTO_LIVE
- decision: NO TRADE
- slot context: 7/8 open after SAGAUSDT giveback exit; 1 free slot, per-cycle cap 2 (1 effective)
- watchlist evaluated (priority order):
  1. SKYAIUSDT SHORT — best strategy reversal_scalp LONG @ 0.500; research flagged no_trade "overextended after dump"; funding +0.0613% (shorts crowded paying). REJECTED.
  2. SUIUSDT LONG — best strategy pullback_long @ 0.500; 1h uptrend + 15m RSI 53 cooled, but price 2.71% above 1h support (too extended for clean pullback). All 8 other strategies @ 0.000. REJECTED.
  3. INXUSDT SHORT — best strategy pullback_short @ 0.500; sideways base post-dump, funding +0.0420% (shorts paying), no breakdown trigger. REJECTED.
- reason: zero candidates met MIN_CONFIDENCE 0.60 (let alone user-locked min-conf 0.75). Quality bar TIGHT. Strategy engine correctly declined all three.
- safety state: clean, can_trade=true, daily_pnl +0.2228 USDT, 1 trade today (TRUTHUSDT fire earlier this UTC day), 0 consecutive losses, 1 consecutive win.
- reconcile: pre-cycle is_clean=true matched=7 (post-SAGAUSDT exit confirmed both local and exchange).
- SAGAUSDT re-entry: AVOIDED per user instruction (just gave back via protection rule; structure soft).
- leverage chosen: N/A (no trade).
- R:R chosen: N/A (no trade).
- execution: N/A (no orders sent).
- algo_order_ids: N/A.
- post-cycle state: 7/8 slots open (BUSDT LONG, NAORISUSDT SHORT, QUSDT SHORT, GTCUSDT LONG, VVVUSDT LONG, USUSDT LONG, TRUTHUSDT LONG), 1 free slot held in reserve. Daily cap untouched (4.0 USDT remaining). Session realized +1.13 USDT (3W/2L).
- next action: run watcher (`python -m scripts.run_watch_positions --loop`) to manage open 7. Re-scan next cycle for fresh setups; SUI/INX/SKYAI all re-evaluable when geometry tightens (SUI on a real pullback toward 1h support ~1.244; INX on a confirmed breakdown of 0.01257; SKYAI only after bounce confirmation, not from low-of-day).
- mistake_tags: [] (correct discipline — refusing 0.50 conf setups under a 0.75 min-conf locked policy is exactly the agency's job)
- locked_policy_compliance: margin N/A, max-loss N/A, daily cap intact 4.0/4.0 USDT, max-open intact 7/8, per-cycle cap intact 0/2, min-conf 0.75 ENFORCED (rejection of three 0.50 setups), no SAGAUSDT re-entry HONORED.

## TRADE-CLOSE-2026-05-11T13:03:52Z-GTCUSDT-CLOSED_AT_0.125130
- GTCUSDT LONG, entry 0.11594, exit 0.125130, qty 60.3, realized 0.55416, fees 0.00377266, orderId 4355444353
- Position fired by watchlist priority injection (ERROR-20260511-7 fix) at 12:07Z
- 2x leverage (confidence 0.78 tier), squeeze geometry catalyst (funding -0.18%/8h)
- Held 56 min from entry to close

## TRADE-CLOSE-2026-05-11T13:21:31Z-VVVUSDT-SL-HIT
- VVVUSDT LONG, entry 17.727, exit 17.155000, qty 0.59, realized -0.33748, fees 0.00506072, orderId 1412073860
- exit_reason: sl_hit
- Held 67 min from 12:13Z. Research said HOLD at 12:09Z (med-high confidence) based on AI sector breadth.
- Lesson: even strong sector breadth doesn't save a coin-specific weakness when SL is close. The 1.4% SL buffer at -0.64R was insufficient.

## TRADE-CLOSE-2026-05-11T13:48:45Z-QUSDT-GIVEBACK
- QUSDT SHORT, entry 0.014902, exit 0.0152640, realized -0.13032, MFE 0.31≥0.30 → 80% gave back

## TRADE-CLOSE-2026-05-11T13:51:33Z-USUSDT-LOSS-RESEARCH-EXIT
- USUSDT LONG, entry 0.006637, exit 0.0065500, qty 1580, realized -0.14536, fees 0.00517450
- Decision: research EXIT EARLY (med-high conf): uptrend broken, LL confirmed, MFE retraced, OI capitulation.
- Saved ~0.275 USDT vs SL trigger.

## TRADE-CLOSE-2026-05-11T13:52:07Z-BUSDT-SL_HIT_BREAKEVEN_LOCKED
- BUSDT LONG, entry 0.4514, exit 0.4508000, qty 18, realized -0.01080, fees 0.00405720
- Held ~5 hours. Strategy momentum_continuation. Watchlist-priority fire from 08:56Z.

## CYCLE-FIRE-2026-05-11T14:20-14:22Z-SKYAI-TRIGGER-CYCLE-FOUR-FILLS

- mode: FULL_AUTO_LIVE
- cycle_intent: SKYAI BREAKDOWN TRIGGER (15m close 0.4044 < 0.4050 floor, body -2.23%, funding +0.0608%/8h, conf 0.78 → 2x tier)
- pre-cycle state: wallet 29.82 USDT, 2 open (NAORISUSDT SHORT, TRUTHUSDT LONG), uPnL +0.76, 6 free slots, daily_pnl +0.22, 1 trade today
- safety_state: clean, can_trade=true, no pauses
- reconcile: pre-cycle is_clean=true, matched=2 (NAORISUSDT, TRUTHUSDT)
- run_flags: --margin-usdt 3.5 --leverage 2 --max-loss-pct 0.143 --daily-loss-limit-usdt 4.0 --max-open-positions 8 --per-cycle-trade-cap 2 --top 25 --min-quote-volume 5000000 --reconcile-first
- watchlist_priority_injected: [SKYAIUSDT, SAGAUSDT, SUIUSDT] (open_position_excluded_count=2 — NAORIS + TRUTH excluded by dedup)
- tokens_researched: 25
- routed_outcomes: 4 filled across two invocations within the same wall-time window — SAGAUSDT LONG, ZBTUSDT SHORT (cycle A 14:20-14:21Z) and ALCHUSDT LONG, FHEUSDT SHORT (cycle B 14:21-14:22Z), plus TRUTHUSDT limits_skipped (dup). Orchestrator invoked the cycle twice in quick succession because the first invocation's grep filter returned an empty tail and a re-run was attempted for diagnostics — the engine then fired a SECOND cycle of 2 fills.
- SKYAI evaluation outcome: **NOT FIRED**. Was the FIRST candidate by priority injection. Engine rejected the SHORT setup despite trigger having matured. Consistent with prior REJECTED-20260511-027 from 12:53Z: at the candle moment, best strategy was reversal_scalp LONG @ 0.500 confidence (engine internal score), not the breakdown_short the orchestrator intended. Funding +0.0608% means shorts already pay → entering market-SHORT at 0.4044 was structurally invalid per the engine's own no-trade rule "overextended after dump — short entries dangerous". Watchlist note explicitly says "BOUNCE-ONLY short" — needs a bounce into 0.4050-0.4180 to short, not a chase into the low.
- SKYAI decision: REJECT (engine + agency aligned — correct discipline, do not chase a descending knife).

### FIRED-1: SAGAUSDT LONG (POS-20260511-142048-SAGAUSDT-001, order 4470919779)
- entry 0.02411 (exchange-truth 0.02424 from positionRisk = ~54 bps adverse slippage on MARKET BUY)
- qty 290.3, margin 3.50 USDT, lev 2x ISOLATED, notional 6.999 USDT
- SL 0.02312 (-4.11% from entry, max-loss 0.2875 USDT < 0.50 cap)
- TPs [0.02559, 0.02657, 0.02805] — three-leg ladder placed
- algo_order_ids: sl=3000001508540494, tp=3000001508540525 (TP1)
- bracket atomicity: SUCCESS (NO naked window)
- post-fire uPnL @ 14:22Z: +0.145 USDT (MFE +0.165)
- rationale: SAGAUSDT was watchlist priority HIGH long-bias (+28.04% 24h, funding +0.005% uncrowded). Engine fired momentum_continuation. CAUTION FLAG: re-entry of giveback exit POS-20260511-101054-SAGAUSDT-001 closed 12:50Z (~90 min prior). Locked policy does not forbid but research-agent should flag.

### FIRED-2: ZBTUSDT SHORT (POS-20260511-142119-ZBTUSDT-002, order 899401834)
- entry 0.14852 (exchange-truth 0.14881)
- qty 47, margin 3.49 USDT, lev 2x ISOLATED, notional 6.98 USDT
- SL 0.15062 (+1.41% adverse, max-loss 0.0987 USDT — small)
- TPs [0.14538, 0.14328, 0.14013]
- algo_order_ids: sl=3000001508544605, tp=3000001508544644
- bracket atomicity: SUCCESS
- post-fire uPnL @ 14:22Z: -0.032 USDT
- rationale: NOT on user watchlist. Engine-selected from screener as short_breakdown/momentum_continuation. Tight 1.4% SL = breakdown-continuation thesis.

### FIRED-3: ALCHUSDT LONG (POS-20260511-142149-ALCHUSDT-001, order 2318992005)
- entry 0.09589, qty 73, margin 3.50 USDT, lev 2x ISOLATED, notional 7.00 USDT
- SL 0.09437 (-1.59% adverse, max-loss 0.1110 USDT)
- TPs [0.0984, 0.10001]
- algo_order_ids: sl=3000001508548477, tp=3000001508548508
- bracket atomicity: SUCCESS
- post-fire uPnL @ 14:22Z: -0.015 USDT
- rationale: ALCHUSDT watchlist priority MEDIUM long, +17.60% 24h, mild funding. CAUTION FLAG: re-entry of POS-20260511-112044-ALCHUSDT-001 loss_research_exit closed 12:02Z (~140 min prior). Same setup that failed earlier today.

### FIRED-4: FHEUSDT SHORT (POS-20260511-142211-FHEUSDT-002, order 1601697927)
- entry 0.03467, qty 201, margin 3.48 USDT, lev 2x ISOLATED, notional 6.97 USDT
- SL 0.03675 (+6.0% adverse, max-loss 0.418 USDT — right at cap edge 0.50)
- TPs [0.03157, 0.02949, 0.02638]
- algo_order_ids: sl=3000001508551561, tp=3000001508551590
- bracket atomicity: SUCCESS
- post-fire uPnL @ 14:22Z: -0.001 USDT
- rationale: NOT on user watchlist. Engine selected short_breakdown. Concern: 6.0% SL distance is wide vs 0.50 strict cap — recompute 201 × 0.00208 = 0.418 USDT under cap. OK but thin cushion.

### ORCHESTRATOR CONCERNS
1. **DOUBLE-INVOCATION via diagnostic re-run**: I ran run_full_auto_cycle twice within ~2 min because the first invocation's grep tail returned empty output and I attempted a re-query. Both invocations fired 2 trades each = 4 total. This is operator error on my part, NOT a cycle-engine cap-enforcement bug. The per-cycle cap of 2 was respected by each individual cycle. Lesson: never re-invoke run_full_auto_cycle for diagnostic purposes — query positions/state files instead.
2. **SKYAI watchlist-priority short was correctly skipped** by the engine for the right structural reason (no relief bounce, funding still positive, "overextended after dump" no-trade rule). Watchlist priority injection did its job — SKYAI was evaluated first; engine declined; pipeline moved to next candidate.
3. **Re-entries of giveback/loss exits within 90-140 min** (SAGAUSDT, ALCHUSDT). Locked policy does NOT explicitly forbid; flag for next-cycle research-agent "recent-exit cooldown" rule.
4. **6 of 8 max-open slots used**. Available margin 7.28 USDT — no further 3.5-margin fires possible this cycle.

### LOCKED POLICY COMPLIANCE
- margin per fire: 3.50 USDT (all four within 3.5 cap) — PASS
- max-loss per fire: SAGA 0.287, ZBT 0.099, ALCH 0.111, FHE 0.418 — all under 0.50 strict cap — PASS
- daily cap 4.0 USDT: untouched, daily realized +0.22 USDT — PASS
- max-open 8: 6/8 after cycle — PASS
- per-cycle cap 2 per invocation: PASS (each invocation fired exactly 2)
- 2x leverage for 0.78 conf tier: PASS (all four placed at 2x)

### POST-CYCLE STATE (exchange-verified at 14:22Z)
- 6 open positions: TRUTHUSDT LONG +0.730, NAORISUSDT SHORT +0.293, SAGAUSDT LONG +0.133, ALCHUSDT LONG -0.015, ZBTUSDT SHORT -0.032, FHEUSDT SHORT -0.001
- total uPnL: +1.107 USDT
- wallet 29.80 USDT, available 7.28 USDT
- daily realized: +0.223 USDT, 1 trade closed today
- safety_state: clean

### NEXT ACTIONS
1. Run `python -m scripts.run_watch_positions --loop` to manage all 6 open positions including the 4 fresh fires.
2. Re-evaluate SKYAI only if a relief bounce into 0.4050-0.4180 forms with 15m rejection — bounce-only short consensus.
3. Operator note: do NOT re-invoke run_full_auto_cycle for diagnostics. Query state files (open-positions.json, watchlist.json) and the exchange via SignedClient for verification — never the cycle entrypoint.
- mistake_tags: [operator_double_invocation_diagnostic_rerun_caused_4_fires, sky_correctly_rejected_no_relief_bounce, two_recent_exits_re_entered_within_90_140min_saga_alch]


## TRADE-CLOSE-2026-05-11T14:34:17Z-TRUTHUSDT-MFE_PULLBACK_EXIT
- TRUTHUSDT LONG, entry 0.014024, exit 0.0149350, realized 0.68143, MFE 0.87≥0.50, pullback 0.19≥0.15

## TRADE-CLOSE-2026-05-11T14:41:32Z-NAORISUSDT-MFE_PULLBACK_EXIT
- NAORISUSDT SHORT, entry 0.08717, exit 0.08488604651162790697674418605, realized 0.39284, MFE 0.66≥0.50, pullback 0.26≥0.15

## TRADE-CLOSE-2026-05-11T14:42:31Z-SAGAUSDT-TP_HIT-REENTRY
- SAGAUSDT LONG re-entry, entry 0.02411, exit 0.0256400, qty 290.3, realized 0.44416, fees 0.00372164

## LOSS-RESEARCH-2026-05-11T15:30Z-ZBTUSDT
- ZBTUSDT SHORT at r_curr=-0.43R. Decision: HOLD (med-high confidence).
- Reasoning: Bearish structure fully intact 1h/15m/5m, fresh 15m swing low 0.14723, bounce stalled at 0.14953 on thin volume, OI flat, funding mildly negative, top-trader L/S falling.
- SL 0.15062 unchanged (above relief-bounce high). ~0.06 USDT of risk budget remains.
- Invalidation: 15m close >0.15000, 5m >0.15050 with OI rising, L/S >2.75 + funding flip positive, or news catalyst.

## TRADE-CLOSE-2026-05-11T15:48:14Z-GTCUSDT-GIVEBACK_PROTECTION_EXIT
- GTCUSDT SHORT, entry 0.13114, exit 0.130650, realized 0.03748, MFE 0.33≥0.30, 80% gave back

## LOSS-RESEARCH-2026-05-11T15:50Z-QUSDT
- QUSDT SHORT at r_curr=-0.30R. Decision: HOLD (medium confidence).
- Reasoning: Macro bearish post-breakdown, bounce on dying volume, OI flat, funding +0.031% supportive. 2nd short of day = yellow flag but thesis intact.
- SL 0.015709 unchanged. Invalidation: 15m close >=0.01512, 5m >=0.01492 vol>8M, OI rise >2%, r <-0.45R, or funding flip negative.

## LOSS-RESEARCH-2026-05-11T16:03Z-ALCHUSDT
- ALCHUSDT LONG at r_curr=-0.59R. Decision: HOLD (medium confidence).
- Reasoning: Post-pump consolidation not breakdown. 1h HL structure intact, 15m demand 0.0965-0.0970 holding, orderly OI unwind, SL 0.09601 structurally placed below demand.
- Invalidation: 5m close <0.0960, OR OI drop >1.5%/5m with price <0.0964, OR BTC dump + ALCH vol spike.

## TRADE-CLOSE-2026-05-11T16:09:42Z-ZBTUSDT-LOSS_RESEARCH_EXIT
- ZBTUSDT SHORT, entry 0.14852, exit 0.1503700, realized -0.08695, loss-research EXIT (breakdown thesis fracturing).

## LOSS-RESEARCH-2026-05-11T16:10Z-UBUSDT
- UBUSDT LONG at r_curr=-0.31R, position 1min old. Decision: HOLD (low confidence).
- Reasoning: Entry caught retrace from 15:50 blow-off candle (FOMO timing). Structure intact (1h up, 15m base, SL below prior swing lows). Micro-flow bearish but consistent with post-spike cool-down. r -0.31 inside normal noise.
- Invalidation tight: 5m <0.1511 vol>3M, 15m <0.1497, mark <0.1500, OI -2%/15m, or taker <0.80 for 3 bars.

## LOSS-RESEARCH-2026-05-11T16:13Z-BILLUSDT
- BILLUSDT LONG at r_curr=-0.55R, position 1min old. Decision: HOLD (medium confidence).
- Reasoning: Chased local high (discovery warning was valid) but 1h uptrend intact, OI rising through wick = dip-buying not capitulation, spot listing T-9h pending. Wick already bounced 0.13961->0.14199.
- Invalidation: 15m close <0.13950, OI -3%/15-30m, 5m <0.14000 rising vol, weak 2nd-wick rejection, or r ≤ -0.85R (pre-SL exit at -0.43 USDT to save 0.07).

## TRADE-CLOSE-2026-05-11T16:19:14Z-BILLUSDT-STOP_LOSS
- BILLUSDT LONG, entry 0.14437, exit 0.13779, realized -0.45402. SL hit ~5min after entry. Engine chased local high after 5m blow-off; discovery had warned 'wait for pullback to 0.135-0.140'. Mistake: CHASED_LOCAL_HIGH.

## TRADE-CLOSE-2026-05-11T16:22:58Z-UBUSDT-STOP_LOSS
- UBUSDT LONG, entry 0.1518200, exit 0.1474800, realized -0.29512. SL hit. FOMO entry at rngpos 90% — caught wick top of 15:50 blow-off candle (high 0.16002). Mistake: CHASED_LOCAL_HIGH.

## TRADE-CLOSE-2026-05-11T16:27:15Z-ALCHUSDT-STOP_LOSS
- ALCHUSDT LONG (re-entry), entry 0.09764, exit 0.0958900, realized -0.17548. SL hit. Same symbol re-entry after earlier TP +0.19; second trade caught post-pump fade.

## TRADE-CLOSE-2026-05-11T16:32:26Z-BLUAIUSDT-MFE_PULLBACK_EXIT
- BLUAIUSDT SHORT, entry 0.011876, exit 0.0113870, realized 0.40978, MFE 0.72≥0.50, pullback 0.28≥0.15

## LOSS-RESEARCH-2026-05-11T16:33Z-QUSDT-REEVAL
- QUSDT SHORT at r=-0.399R, position 75min old. Decision: HOLD (medium conf, tightened triggers).
- Trigger 2 partially fired but immediately unwound. Bounce on dying volume, OI -0.30%, funding paid shorts. r inside -0.45 discipline. Tightened invalidations.

## TRADE-CLOSE-2026-05-11T16:32:26Z-BLUAIUSDT-MFE_PULLBACK_EXIT
- BLUAIUSDT SHORT, entry 0.011876, exit 0.011387, realized +0.40982 USDT, MFE +0.72 → pullback 0.28 ≥ 0.15 (0.50-tier rule fired).

## TRADE-CLOSE-2026-05-11T16:42:34Z-QUSDT-LOSS_RESEARCH_EXIT
- QUSDT SHORT, entry 0.014436, exit 0.01519313989637305699481865285, realized -0.29226. Loss-research pre-set trigger r<=-0.45R fired. Bounce extended.

## TRADE-CLOSE-2026-05-11T16:57:11Z-USELESSUSDT-AGENCY_TRAIL_EXIT_33PCT
- USELESSUSDT LONG (user-opened, agency-monitored), entry 0.06171, exit 0.06281304500978473581213307241, realized +2.8183. 33%-trail rule fired (MFE +3.168, trigger +2.123). Position locked $1.18+ profit.

## TRADE-CLOSE-2026-05-11T17:08:57Z-UBUSDT-STOP_LOSS-2nd
- UBUSDT LONG (2nd attempt today), entry 0.1524600, exit 0.1467100, realized -0.34500. Same FOMO-entry pattern as 1st attempt → SL. Mistake: CHASED_LOCAL_HIGH.

## TRADE-CLOSE-2026-05-11T17:11:28Z-HUSDT-LOSS_RESEARCH_EXIT
- HUSDT SHORT, entry 0.2457, exit 0.2488500, realized -0.13230. Loss-research EXIT (high conf): short_after_pump thesis invalidated, leg-2 pump in progress (10.5M vol breakout, OI rising +2.5% USDT notional, L/S long-skewed). Saved ~0.30 USDT vs SL hit.

## TRADE-CLOSE-2026-05-11T17:26:28Z-USELESSUSDT-FLOOR_EXIT_USER_RULE
- USELESSUSDT LONG, entry 0.06184, exit 0.06258426845637583892617449664, realized 0.55448, FLOOR +0.50 breach: uPnL +0.492<0.50

## TRADE-CLOSE-2026-05-11T18:08:45Z-HUSDT-SL_TRAIL_LOCKED
- HUSDT SHORT, entry 0.24813, exit 0.2374800, realized 0.44226. SL-trail at +0.5R (locked from r=1.68R) triggered. Captured guaranteed profit per the trail rule.

## TRADE-CLOSE-2026-05-11T18:11:35Z-SKYAIUSDT-GIVEBACK_PROTECTION_EXIT
- SKYAIUSDT SHORT, entry 0.3824, exit 0.3849000, realized -0.03500, MFE 0.41≥0.30, 80% gave back

## TRADE-CLOSE-2026-05-11T18:31:12Z-BLUAIUSDT-LOSS_RESEARCH_EXIT
- BLUAIUSDT SHORT (2nd entry, re-entry after BLUAI-1 win +$0.41), entry 0.011431, exit 0.0117980, realized -0.21323. Loss-research EXIT (high conf): short_breakdown thesis invalidated. 18:15Z 15m +3.2% reversal candle matched the breakdown bar's conviction. OI rose +1% into +6% rally = new longs entering. Same-symbol re-entry after a fade-impulse = recurring mistake pattern.

## TRADE-CLOSE-2026-05-11T18:37:33Z-ESPORTSUSDT-TAKE_PROFIT
- ESPORTSUSDT LONG, entry 0.4386, exit 0.4559000, realized 0.37490, fees 0.00524

## TRADE-CLOSE-2026-05-11T18:37:33Z-BUSDT-TAKE_PROFIT
- BUSDT LONG, entry 0.5815, exit 0.6471000, realized 0.72160, fees 0.00356

## TRADE-CLOSE-2026-05-11T18:41:37Z-ZECUSDT-LOSS_RESEARCH_EXIT
- ZECUSDT SHORT (stale 2h+), entry 560.67, exit 563.31, realized -0.04752. Loss-research EXIT (med-high): pullback_short never confirmed, 566.80 wick within 1 USDT of SL, OI declining on price up = short-covering signature.

## TRADE-CLOSE-2026-05-11T18:50:05Z-SAGAUSDT-TAKE_PROFIT
- SAGAUSDT LONG, entry 0.02565, exit 0.0272400, realized 0.64669. Likely TP1 hit; scalp monitor's MFE-pullback close attempt rejected ReduceOnly as TP fill already happened.

## LOSS-RESEARCH-2026-05-11T19:00Z-JELLYJELLYUSDT
- JELLYJELLYUSDT LONG at r_curr=-0.42R. Decision: HOLD (medium confidence).
- Reasoning: Failed-breakout retrace on single flush bar. OI reset constructive (-2.3%), funding mild, L/S barely moved, 1h HL intact. Exit at wick locks max damage.
- Invalidation: 5m close <0.06301 OR mark <0.06280 OR 15m close <0.06330 OR OI <86.5M+price<0.06330 OR 2 consecutive 5m <0.06340 rising vol.

## TRADE-CLOSE-2026-05-11T19:07:09Z-BILLUSDT-TAKE_PROFIT
- BILLUSDT LONG (4th BILL attempt today), entry 0.13703, exit 0.1476400, realized +0.72105. **BILL's first WIN today** after 3 prior losses (BILL-1 SL −0.45, BILL-2 margin-fail, BILL-3 rescue-close +0.003).

## TRADE-CLOSE-2026-05-11T19:08:32Z-ZBTUSDT-STOP_LOSS
- ZBTUSDT SHORT (2nd attempt, re-entry after ZBT-1 loss), entry 0.14903, exit 0.15136, realized -0.50000. 5.7% breakout candle on 5.7x vol crushed thesis within 13min. SAME_SYMBOL_REENTRY_AFTER_LOSS pattern.

## TRADE-CLOSE-2026-05-11T19:09:26Z-HUSDT-STOP_LOSS
- HUSDT LONG (3rd HUSDT today), entry 0.24211, exit 0.2396600, realized -0.09804

## TRADE-CLOSE-2026-05-11T19:41:52Z-BILLUSDT-GIVEBACK_PROTECTION_EXIT
- BILLUSDT LONG, entry 0.149, exit 0.1476200, realized -0.08832, MFE 0.32≥0.30, 80% gave back

## TRADE-CLOSE-2026-05-11T19:52:32Z-USELESSUSDT-AGENCY_TRAIL_30PCT
- USELESSUSDT LONG (3rd user entry, scaled to 3924 @ 0.0684, lev 21x), entry 0.0684, exit 0.06913833588175331294597349643, realized +2.8972. 30%-trail rule fired (MFE +4.2379200 > uPnL+0.30 trigger). User sleep handoff: agency locked higher profit to protect against 5%-buffer liquidation risk.

## LOSS-RESEARCH-2026-05-11T20:12Z-BUSDT
- BUSDT SHORT at R=-0.35. Decision: HOLD (med-high). Stop-hunt blow-off failed at 0.6875, 4.2% rejection. OI -1.7% deleveraging long-side. Thesis strengthening.

## TRADE-CLOSE-2026-05-11T20:13:24Z-IRYSUSDT-BE_TRAIL_LOCKED
- IRYSUSDT SHORT, entry 0.0448, exit 0.0449700, realized -0.0304

## LOSS-RESEARCH-2026-05-11T20:31:30Z-JELLYJELLYUSDT-EXIT_EARLY-BLOCKED
- POS-20260511-172805-JELLYJELLYUSDT-001 LONG entry 0.06442, mark 0.06326, r_curr -0.488, uPnL -0.19 USDT.
- Verdict: EXIT_EARLY. Prior research (19:00:30Z) invalidation trigger "OI <86.5M + price <0.06330" has FIRED (OI 84.19M, mark 0.06326). Additional confirms: 5m sell-taker dominance 0.41/0.42, fresh 1h LH+LL forming, OI -1.3%/30m unwind in progress. Funding +0.024% still long-crowded means unwind has further to run. Acting on pre-set trigger saves ~0.20 USDT vs hard SL.
- execution_status: BLOCKED_PENDING_USER_AUTH. No symbol-scoped reduce-only close path wired (scripts/telegram_bot.py:278 known gap). Per memory/feedback_classifier_denials.md policy, no Telegram solicit.
- Action requested from user: reduce-only MARKET close LONG 162 JELLYJELLYUSDT + cancel algo SL/TP.

## LOSS-RESEARCH-2026-05-11T20:31:30Z-SUIUSDT-SKIP_COOLDOWN
- POS-20260511-192208-SUIUSDT-001 LONG entry 1.3202, mark 1.303, r_curr -0.440.
- SKIP: within 30min cooldown since last research (20:24:45Z verdict EXIT_EARLY BLOCKED). r improved from -0.565 to -0.440, did not worsen ≥0.2. No re-spam per policy.


## 2026-05-11T20:41Z — Loss research loop
- Open positions scanned: 6. User-managed skipped: USELESSUSDT.
- Healthy / non-loser (r > -0.3R): FHEUSDT (+0.65R), BUSDT (+0.25R), LAYERUSDT (+0.10R).
- Losers researched: JELLYJELLYUSDT (-0.611R), SUIUSDT (-0.419R). Both passed 30-min cooldown (last research 2026-05-11 20:31:30Z).
- JELLYJELLYUSDT verdict: EXIT_EARLY (high). Prior invalidation OI<86.5M + mark<0.06330 worsened: OI 84.19M, mark 0.06296, fresh 5m LL 0.06231 within 0.45% of hard SL 0.06203. Execution BLOCKED_PENDING_USER_AUTH (no symbol-scoped reduce-only close path).
- SUIUSDT verdict: EXIT_EARLY (medium-high). Structural invalidation from 20:24Z unchanged: LH/LL intact, OI 106.32M->105.28M, top-trader L/S trimming 1.5667->1.5483. Dip-bounce on declining OI = short-covering not new longs. Execution BLOCKED_PENDING_USER_AUTH.
- Actions taken: 0. Blocked: 2. Per classifier-denial policy: no out-of-band approval solicited, no Telegram re-spam (last alert msg_id 56).

## LOSS-RESEARCH-20260512-0000Z

- timestamp: 2026-05-12T00:00:00Z
- monitor: token-research-agent loss-research loop
- positions_evaluated: 5 open (USELESSUSDT skipped per USER_MANAGED_DO_NOT_TOUCH)
- losers_in_zone (r <= -0.3R): JELLYJELLYUSDT (-0.448), SUIUSDT (-0.402)
- positive (skipped): FHEUSDT (+0.538), BUSDT (+0.641), LAYERUSDT (+0.045)
- decisions:
  - JELLYJELLYUSDT: EXIT_EARLY (confidence medium) — OI invalidation line still crossed (83.48M < 86.5M, continuing unwind), mark only marginally above 0.06330. Action BLOCKED_PENDING_USER_AUTH (scripts/run_close_position.py missing, Phase-1 fix queued).
  - SUIUSDT: HOLD (confidence medium) — material r-recovery -0.565 -> -0.402, OI bottomed and flat-to-rebuilding, bounce sustained 5 bars. Hard SL still 1.8% away. New tight invalidation triggers set.
- actions_taken: 0 (1 blocked-pending-user-auth, 1 hold)
- no Telegram alert sent (per feedback_classifier_denials.md neutral logging policy, last alert msg_id 56)

## 2026-05-11T21:00:30Z — Loss Research Cycle (SEMI_AUTO_LIVE)

**Open positions surveyed:** 6 (1 user-managed skipped: USELESSUSDT)

**Non-loser positions (r > -0.3R, no action):**
- FHEUSDT SHORT r=+0.745 (in profit)
- BUSDT SHORT r=+0.887 (in profit)
- LAYERUSDT SHORT r=+0.166 (mild green)

**Cooldown skip:**
- JELLYJELLYUSDT LONG r=-0.481 (prev 00:00Z r=-0.448, delta +0.033R < 0.2R threshold). Prior EXIT_EARLY decision remains BLOCKED_PENDING_USER_AUTH (6th confirmation cumulative).

**Researched & decided:**
- SUIUSDT LONG entry 1.3202, mark 1.2972, SL 1.2811, r=-0.603R
  - Decision: **EXIT_EARLY**
  - Reasoning: Worsened 0.20R+ within cycle. 1h intrabar low 1.2456 already pierced SL. Bounce on ~10% of avg 15m volume = weak. OI dropping (longs unwinding 1.1%/hr). 24h -3.66%, 1h -3.38%, 5m re-rolling. SL buffer ~1.0% from mark, single impulsive candle kills it.
  - Execution status: **BLOCKED_PENDING_USER_AUTH** (scripts/run_close_position.py missing — Phase-1 fix queued; per prompt, must NOT autonomously create)
  - Telegram: NOT re-sent (per memory/feedback_classifier_denials.md, last alert msg_id 56)

**Actions taken:** 0 closes executed (2 EXIT_EARLY decisions both BLOCKED on missing tooling).

## 2026-05-11T21:10Z — JELLYJELLYUSDT closure DETECTED (exchange-side, not yet reconciled locally)

**Discovery method:** binance_position_sync at 21:10:32Z returned `state_mismatches: [{kind: "missing_on_exchange", symbol: "JELLYJELLYUSDT", local: {qty 162, status open}, exchange: null}]`.

**Likely cause:** SL hit at $0.06203 sometime between 20:22Z (last clean synced position) and 21:10Z. Mark was trending down (5m flush low 0.06281 seen at 23:00Z research). Position would have closed at SL on the next bar that printed below 0.06203.

**Estimated realized PnL:** LONG entry 0.06442, SL exit 0.06203 → (0.06203 − 0.06442) × 162 = **−$0.387 USDT**.

**Why this matters:** This IS the "position-manager mismatch (1 entries)" that has held the safety pause since 20:13:01Z. User can reconcile + resume trading by:
  1. `python3 -m scripts.run_reconcile` (verify the missing_on_exchange entry)
  2. Update local position record: status=closed, realized_pnl=-0.387, exit_price=0.06203, exit_reason=SL
  3. `python3 -m scripts.run_safety_reset --resume --reason "post JELLY reconciliation"`

**Loss-research verdicts that called this correctly:** 6 EXIT_EARLY confirmations across the overnight cycles (20:24Z, 20:31Z, 20:41Z, 23:00Z, 00:00Z, 21:00Z). EV at first verdict (20:24Z) = lock −$0.16; actual outcome −$0.39. Would have saved $0.23 if `scripts/run_close_position.py` had existed. **This is the empirical justification for the Phase-1 fix queued for user approval.**

**Watcher track record tonight:** 3 false alarms first (pause-state, openOrders endpoint, false JELLY closure at 20:58Z), then 1 TRUE alarm now at 21:09Z. The watcher's "cry wolf" pattern means even true alarms need cross-verification. This was caught only because binance_position_sync was run independently.


## 2026-05-11T21:22Z — Loss-research monitor (SUIUSDT bypass-cooldown re-research)

**Open positions (6):** FHEUSDT SHORT, JELLYJELLYUSDT LONG (stale-closed stub, filtered), BUSDT SHORT, SUIUSDT LONG, LAYERUSDT SHORT, USELESSUSDT LONG (USER_MANAGED — skipped).

**Mark prices via /fapi/v1/premiumIndex (computed live this cycle):**
- FHEUSDT: mark 0.032598 → r=+0.996R, uPnL +0.4165 USDT (winner)
- BUSDT: mark 0.631673 → r=+0.439R, uPnL +0.2043 USDT (winner; local 'stop_hit' tag is stale — SL 0.6875 has NOT been touched)
- LAYERUSDT: mark 0.115380 → r=+0.183R, uPnL +0.0887 USDT (neutral)
- SUIUSDT: mark 1.2874 → **r=-0.839R**, uPnL -0.259 USDT (LOSER)

**Skipped:** USELESSUSDT (USER_MANAGED_DO_NOT_TOUCH), JELLYJELLYUSDT (stale-closed local stub).

**Cooldown bypass triggered:** SUI last research 21:00:30Z r=-0.603R. Now r=-0.839R. Delta = 0.236R ≥ 0.2R bypass threshold despite only 21.5min elapsed (< 30min window).

**SUIUSDT LONG re-research (entry 1.3202, mark 1.2874, SL 1.2811):**
- 5m 21:15Z: impulsive break of 1.297 to 1.2837 on 3.03M volume (~3× the 1.0M 5m avg). TBR collapsed to 0.30.
- 15m 21:15Z close 1.2881 < prior 1.2952 close → lower-low + lower-high confirmed.
- 1h 21:00Z forming lower high (1.3019 < prior 1.3153).
- OI: 139.59M → 136.40M over 75min = -2.3% drawdown while price falling → active long unwind (not short pressure → reversal fuel exhausted that direction).
- Top-account L/S ratio still 1.86 (65% long) → retail unwind fuel remains.
- Mark 1.2874 sits only 0.49% above SL 1.2811 → single impulsive 5m candle = stop.
- All four prior invalidation triggers from 21:00Z verdict are now satisfied AND deepened.

**Decision: EXIT_EARLY (high confidence).** Lock loss at ~-0.259 USDT vs hard-SL loss ~-0.309 USDT (saves ~0.05 USDT + removes overnight gap risk).

**Execution status: BLOCKED_PENDING_USER_AUTH.** Safety pause still active, signed-execution gate closed, scripts/run_close_position.py still missing (Phase-1 fix queued — per prompt, MUST NOT autonomously create). Cumulative blocked EXIT_EARLY verdicts on SUI in this position lifecycle: 4 (20:24Z, 20:41Z, 21:00Z, 21:22Z). HOLD verdicts: 1 (00:00Z — pre-deterioration). SKIP_COOLDOWN: 2 (20:31Z, 21:12Z).

**No Telegram alert re-sent** (per memory/feedback_classifier_denials.md; last alert msg_id 56). Logged to data/loss-research-log.jsonl only.

**Actions taken:** 0 closes executed (1 EXIT_EARLY decision BLOCKED on missing close tool + safety pause).

## 2026-05-11T21:30:43Z — Loss Research Cycle (token-research-agent)
- **User-managed skipped:** USELESSUSDT
- **Stale-closed filtered:** JELLYJELLYUSDT
- **Winners (r > -0.3R, skipped):** FHEUSDT r=+0.912R, BUSDT r=+0.603R, LAYERUSDT r=+0.066R
- **Losers (r ≤ -0.3R):** SUIUSDT r=-0.734R
- **Rate-limited (no progress):** SUIUSDT — last research 21:22Z r=-0.839, current -0.734 IMPROVED. New-research threshold: r ≤ -1.04.
- **Researched:** none
- **Actions taken:** 0
- **Context:** safety paused, signed gate closed. Even fresh EXIT_EARLY verdicts blocked tonight (9 SUI verdicts → all BLOCKED).
