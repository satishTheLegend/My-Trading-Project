# Execution Errors

Log of every Binance API error, partial fill anomaly, stop-placement failure, precision issue, or unexpected exchange response.

## Format

```
## ERROR-YYYYMMDD-N

- timestamp:
- mode:
- symbol:
- attempted_action: set_leverage | set_margin_mode | place_entry | place_stop | place_tp | reduce_only_close | cancel | other
- binance_code:
- binance_message:
- internal_state:
- exchange_state:
- impact: blocked_entry | open_without_protection | duplicate_position | reconciliation_required | cosmetic
- resolution:
- escalated_to: safety-agent | risk-manager | user | none
```

Never include API keys or secrets in this file.

## ERROR-20260511-1

- timestamp: 2026-05-11T08:24:20Z
- mode: FULL_AUTO_LIVE
- symbol: SUIUSDT
- attempted_action: other (state reconciliation after user-initiated manual close)
- binance_code: n/a
- binance_message: n/a
- internal_state: open SHORT 4.5 @ 1.3256 since 2026-05-10T18:16:36Z, SL 1.365, TPs [1.2634, 1.2228, 1.1618]
- exchange_state: flat (zero position, zero open orders)
- impact: reconciliation_required
- resolution: queried /fapi/v1/userTrades + /fapi/v1/order. Closing order 38865339146 (clientOrderId prefix ios_, type=MARKET, reduceOnly=true) fired by user from Binance iOS app at 2026-05-11T01:53:19Z. Two fills @ 1.3348 covering full 4.5 qty. Realized PnL -0.04230 USDT (pre-commission), commission 0.00300330 USDT. Exit price 1.3348 is above entry (loss on a SHORT) but well below SL 1.365 and not at any TP - classified as manual_close_by_user_ios. data/open-positions.json updated: status=closed, exit_price, exit_reason, closed_at, realized_pnl, fees_paid_usdt set. Re-ran binance_position_sync: clean, new_trades_allowed=true. Also updated data/system-health.json (last_reconciliation_clean=true, mismatch_count=0).
- escalated_to: user (informational - user already knew, this is just state alignment)

## ERROR-20260511-2

- timestamp: 2026-05-11T08:24:20Z
- mode: FULL_AUTO_LIVE
- symbol: DEEPUSDT
- attempted_action: other (state reconciliation after user-initiated manual close)
- binance_code: n/a
- binance_message: n/a
- internal_state: open SHORT 136 @ 0.044 since 2026-05-10T18:25:35Z, SL 0.04538, TPs [0.04185, 0.04044, 0.03832]
- exchange_state: flat (zero position, zero open orders)
- impact: reconciliation_required
- resolution: queried /fapi/v1/userTrades + /fapi/v1/order. Entry order 843995801 actually filled at 0.04385 (not 0.044 as locally recorded - local was the planned entry, exchange truth corrected on close). Closing order 847048184 (clientOrderId prefix ios_, type=MARKET, reduceOnly=true) fired by user from Binance iOS app at 2026-05-11T01:53:17Z. Single fill @ 0.04197 for 136 qty. Realized PnL +0.25568 USDT (pre-commission), commission 0.00583576 USDT. Exit 0.04197 is just 0.00012 above (worse than) TP1 0.04185 and well below SL 0.04538 - classified as manual_close_by_user_ios near TP1. data/open-positions.json updated: status=closed, entry_price corrected to 0.04385, exit_price, exit_reason, closed_at, realized_pnl, fees_paid_usdt set.
- escalated_to: user (informational)

## ERROR-20260511-3

- timestamp: 2026-05-11T08:24:20Z
- mode: ANY
- symbol: n/a
- attempted_action: other (sync agent observation)
- binance_code: n/a
- binance_message: n/a
- internal_state: n/a
- exchange_state: n/a
- impact: cosmetic
- resolution: Both SUIUSDT and DEEPUSDT manual closes were executed by the user within a 2-second window (01:53:17Z and 01:53:19Z on 2026-05-11) from the Binance iOS app, while the agency was sleeping/idle between cycles. This is the expected manual-position pattern. New-trades gate was correctly held closed by binance_position_sync until reconciliation completed. Wallet at 29.18 USDT (user topped up from ~12 USDT after these closes). Recommend: future cycles should call /fapi/v1/userTrades when a local-open / exchange-flat mismatch is detected, so this reconciliation can be automated rather than manual.
- escalated_to: none

## ERROR-20260511-4

- timestamp: 2026-05-11T09:18:24Z (incident); 2026-05-11T09:53:00Z (fix)
- mode: FULL_AUTO_LIVE
- symbol: BUSDT
- attempted_action: other (watcher trailing-stop + local exit-decision logic)
- binance_code: n/a
- binance_message: n/a
- internal_state: at 09:18:24Z the watcher marked POS-20260511-085626-BUSDT-001 as status=closed, exit_reason=stop_hit, closed_at=09:18:24Z, quantity=0, after the watcher's trailing logic had ratcheted the LOCAL stop_loss field upward (final value 0.4640079) and a subsequent candle's low broke that locally-trailed (but exchange-unknown) level.
- exchange_state: at 09:44:51Z binance_position_sync confirmed the BUSDT LONG was still open on Binance at 18 qty @ entry 0.4514, mark ~0.4727, uPnL +0.38 USDT, with the ORIGINAL bracket orders intact: SL algoId 3000001506269526 @ 0.4264 (algoStatus=NEW) and TP algoId 3000001506269544 @ 0.5189 (algoStatus=NEW). The exchange had NEVER been told about any of the local trailing-stop moves.
- impact: open_without_protection (almost — exchange SL/TP were still active, so capital was protected; what was almost lost was the *trade* itself, by being abandoned in local state while still live at Binance and uPnL +0.38 USDT)
- resolution: Surgical fixes to the watcher/exit pipeline (scripts/watcher.py, scripts/exit_simulator.py, scripts/positions_store.py, scripts/live_execution.py, scripts/run_watch_positions.py):
  1. Added a first-class `algo_order_ids: dict[str, str]` field on `Position` (positions_store.py) so the watcher can find the SL algoId without parsing notes. `from_jsonable` defaults to `{}` for backward compatibility.
  2. Introduced LIVE_MODES = {SEMI_AUTO_LIVE, FULL_AUTO_LIVE} in exit_simulator.py. In LIVE_MODES, `apply_decision` REFUSES to mutate state for any local-price terminal decision (STOP_HIT, FULL_TP, PARTIAL_TP, INVALIDATION_EXIT) — it appends a `live_mode_skipped_local_exit:...` note and returns a no-op AppliedExit. Closures in live mode are written only after binance_position_sync confirms zero qty on the exchange, OR a reduce-only fill arrives on a known algoId, OR the user/safety agent explicitly closes via run_emergency_close.
  3. In LIVE_MODES, `apply_decision` REFUSES to move the local stop_loss for TRAIL_STOP / MOVE_STOP_BREAKEVEN without an exchange-side algoOrder replace. A `live_mode_trail_blocked:...` note is appended instead.
  4. Added two algo-order helpers to live_execution.py: `place_algo_stop_market` (POST /fapi/v1/algoOrder, reduce-only STOP_MARKET, MARK_PRICE, priceProtect) and `cancel_algo_order` (DELETE /fapi/v1/algoOrder, by algoId). These wrap the post-2025-12-09 endpoint migration.
  5. Rewrote `watcher.py` to (a) make trailing OPT-IN via the `EXIT_TRAILING_STOP_ENABLED` env var (default FALSE), (b) when trailing is enabled in live mode, route through a new `_try_live_trailing` helper that cancels the existing SL algoOrder THEN places the new one before touching local state — any failure leaves both exchange and local state unchanged AND surfaces a SAFETY-CRITICAL warning if the failure happens between cancel and place (naked-position window), (c) accept an optional pre-fetched `exchange_positions` snapshot and emit SAFETY warnings on any local-open / exchange-flat or side-mismatch divergence, (d) suppress the synthetic safety-event journal write for emergency_exit in live mode (the real safety event is written by emergency_close.py).
  6. Updated run_watch_positions.py CLI to fetch the exchange snapshot when credentials are present (opt-out via `--no-exchange-guardrail`) and to support an `--enable-trailing` flag that overrides the env var.
- escalated_to: safety-agent (re-enabling trailing after operator validates the cancel-and-replace path on a small test position), user (informational — recovery details). Verification: all 198 unit tests pass; live tick at 09:53:29Z returns decision=hold for BUSDT and persists status=open/qty=18/SL=0.4264; binance_position_sync at 09:53:43Z returns sync_status=success new_trades_allowed=true with no mismatches; 3 sequential ticks at 2s intervals produced 3 hold decisions with zero mutations to status/closed_at/exit_*; targeted scenario test confirmed (i) live STOP_HIT no longer closes locally, (ii) paper STOP_HIT still closes (no regression), (iii) live TRAIL_STOP without executor does NOT move local SL.

## ERROR-20260511-5

- timestamp: 2026-05-11T10:10:54Z (entry); 2026-05-11T10:12:06Z (manual remediation)
- mode: FULL_AUTO_LIVE
- symbol: SAGAUSDT
- attempted_action: place_protective_orders (post-entry bracket placement by execution_router)
- binance_code: n/a (router never reached the call)
- binance_message: n/a
- internal_state: Position recorded with status=open, quantity=482.6, stop_loss=0.02291, take_profit_targets=[0.0254, 0.02639, 0.02788], BUT algo_order_ids={} (no brackets placed).
- exchange_state: SAGAUSDT positionRisk shows 482.6 qty @ entryPrice 0.02386, uPnL +0.024 at first check (later moved to -0.10), liq 0.01633. /fapi/v1/openAlgoOrders returned [] (NAKED). /fapi/v1/openOrders also [].
- impact: open_without_protection (CRITICAL — position naked for ~3 min between MARKET fill and orchestrator-side remediation)
- resolution: Orchestrator placed SL+TP directly via /fapi/v1/algoOrder bypassing the broken live_execution.place_algo_stop_market helper:
  - SL: POST /fapi/v1/algoOrder with side=SELL, algoType=CONDITIONAL, type=STOP_MARKET, triggerPrice=0.0229100, quantity=482.6, reduceOnly=true, workingType=MARK_PRICE, priceProtect=true, clientAlgoId=SL-PROP-20260511-SAGA-001. Returned algoId 3000001506760168 algoStatus=NEW.
  - TP: POST /fapi/v1/algoOrder with side=SELL, algoType=CONDITIONAL, type=TAKE_PROFIT_MARKET, triggerPrice=0.0263900, quantity=482.6, reduceOnly=true, workingType=MARK_PRICE, priceProtect=true, clientAlgoId=TP-PROP-20260511-SAGA-001. Returned algoId 3000001506760194 algoStatus=NEW.
  - Verified via /fapi/v1/openAlgoOrders: both NEW, both reduceOnly=true, MARK_PRICE, priceProtect=true, quantity 482.6 each.
  - data/open-positions.json updated: algo_order_ids={"sl":"3000001506760168","tp":"3000001506760194"}, mistake_tags include execution_router_missing_protective_orders + naked_between_fill_and_bracket, full forensic notes appended.
  - Re-ran binance_position_sync: sync_status=success, manual_positions_detected=[], state_mismatches=[], new_trades_allowed=true.
- pattern_recognition: THIRD consecutive FULL_AUTO_LIVE cycle to fire entry without brackets (BUSDT cycle #4 morning of 11 May; LABUSDT 10:02:00Z; SAGAUSDT 10:10:54Z). live_execution.place_algo_stop_market still ships the legacy schema (stopPrice/newClientOrderId/type=STOP_MARKET, NO algoType) which Binance rejects with -1102 "Mandatory parameter algotype not sent" since the 2025-12-09 algoOrder endpoint migration. The execution_router's catch-and-continue around the helper failure leaves the entry filled but the brackets absent. THIS BUG MUST BE FIXED BEFORE NEXT FULL_AUTO_LIVE CYCLE.
- required_fix: Migrate scripts/live_execution.py:place_algo_stop_market AND add equivalent place_algo_take_profit_market to:
  - send algoType="CONDITIONAL" (mandatory)
  - rename stopPrice -> triggerPrice
  - rename newClientOrderId -> clientAlgoId
  - keep reduceOnly=true, workingType=MARK_PRICE, priceProtect=true, quantity, symbol, side
  - tighten execution_router so a bracket-placement failure cancels the position via reduce-only MARKET exit AND escalates to Safety Agent rather than leaving the position naked.
  - Add unit test that exercises the bracket POST and asserts the request body contains algoType, triggerPrice, clientAlgoId.
- escalated_to: safety-agent (informational — protection now in place); error-fix-agent (must own the helper migration + router hardening); user (informational — recurring gap, three trades in a row).

## ERROR-20260511-5-RESOLUTION

- timestamp: 2026-05-11T10:30:00Z
- mode: code-fix (no live trades issued by this work; verified against mainnet via single read-only-failing probe)
- symbol: n/a (systemic fix)
- attempted_action: migrate place_algo_stop_market + add place_algo_take_profit_market + harden execution_router post-entry flow
- binance_code: dry-run probe returned -1111 "Precision is over the maximum defined for this asset" (NOT -1102) — confirms new schema is parsed by Binance
- binance_message: see above
- internal_state: bug fix only, no internal trade state mutated; 3 open positions (BUSDT, LABUSDT, SAGAUSDT) untouched
- exchange_state: 3 open positions confirmed via binance_position_sync at 2026-05-11T10:28:38Z — sync_status=success, manual_positions_detected=[], state_mismatches=[], new_trades_allowed=true. Wallet 29.16197507 USDT, available 19.61575958 USDT.
- impact: blocked_entry (this fix prevents the bug; previous naked windows already remediated by orchestrator)
- resolution: Six surgical changes applied:
  1. scripts/live_execution.py:place_algo_stop_market — rewrote to send the post-2025-12 algoOrder schema. Params now include algoType=CONDITIONAL, type=STOP_MARKET, triggerPrice (was stopPrice), clientAlgoId (was newClientOrderId), positionSide=BOTH, timeInForce=GTC, plus the previous reduceOnly=true / workingType=MARK_PRICE / priceProtect=true / quantity / symbol / side. Python kwarg names kept (stop_price, client_order_id) so the watcher's existing call site continues to work unchanged.
  2. scripts/live_execution.py:place_algo_take_profit_market — NEW symmetric helper; same wire schema with type=TAKE_PROFIT_MARKET. Returns OrderResult with algoId in order_id and clientAlgoId in client_order_id (via _to_result fallback).
  3. scripts/live_execution.py:cancel_algo_order — already existed; unchanged.
  4. scripts/live_execution.py:_to_result — extended to read clientAlgoId / orderType / algoStatus fields when present.
  5. scripts/execution_router.py — added _place_brackets_or_rescue + _rescue_naked_entry. After every live MARKET entry fill, the router now atomically places SL via place_algo_stop_market THEN TP via place_algo_take_profit_market. On either failure, it best-effort cancels any successfully-placed bracket, issues a reduce-only MARKET close, calls safety.pause(carry_over_rollover=true), and appends a SAFETY-NAKED-* event to memory/safety-events.md via append_safety_event. Returns status='naked_rescued' with algo_order_ids={}. On both-success, returns status='filled' with algo_order_ids={'sl':..., 'tp':...}. ExecutionOutcome gained an algo_order_ids field.
  6. scripts/run_full_auto_cycle.py + scripts/run_live_cycle.py — pass safety=safety into ExecutionRouter constructor; populate Position.algo_order_ids from outcome.algo_order_ids on filled status; on naked_rescued status, break out of the proposal loop (do NOT persist a Position, do NOT keep firing).
- tests: 5 new tests in tests/ — three new naked-rescue tests in test_execution_router.py (SL-fail, TP-fail, missing-brackets-input), one happy-path test asserting algoIds populate and no rescue path triggers, plus three new tests in test_live_execution.py asserting the wire payload contains algoType=CONDITIONAL, type=STOP_MARKET|TAKE_PROFIT_MARKET, triggerPrice, clientAlgoId, positionSide=BOTH, and that the legacy fields (stopPrice, newClientOrderId) are NOT sent. Full suite: 205 passed, 5 skipped (smoke tests gated on live API), 0 failed.
- dry_run_probe: POST /fapi/v1/algoOrder against AVAXUSDT mainnet with side=SELL, type=STOP_MARKET, triggerPrice=999999, quantity=0.001, reduceOnly=true, no AVAX position held. Binance response code=-1111 "Precision is over the maximum defined for this asset." This is the expected outcome for the probe — Binance parsed every mandatory parameter and rejected only on numeric content. We did NOT receive -1102 (mandatory-parameter-not-sent), which is the diagnostic signal the prompt asked for. The probe confirms the new schema reaches Binance's filter layer instead of being bounced at the parameter-validation layer.
- post_fix_sync: python3 -m scripts.binance_position_sync at 2026-05-11T10:28:38Z returned sync_status=success, open_positions_count=3, manual_positions_detected=[], state_mismatches=[], new_trades_allowed=true. BUSDT / LABUSDT / SAGAUSDT remain open and protected.
- files_changed:
  - scripts/live_execution.py (helper migration + new TP helper + _to_result tweak)
  - scripts/execution_router.py (atomic bracket placement + naked-rescue + safety integration)
  - scripts/run_full_auto_cycle.py (wire safety into router, propagate algo_order_ids, handle naked_rescued)
  - scripts/run_live_cycle.py (same as above for SEMI_AUTO_LIVE entrypoint)
  - tests/test_live_execution.py (new schema assertions + cancel-algo test)
  - tests/test_execution_router.py (FakeLiveExecution extended with bracket helpers + 4 new tests)
- escalated_to: user (informational — fix landed, ready for next FULL_AUTO_LIVE cycle); safety-agent (informational — naked-rescue path will pause trading automatically on any future bracket failure, no operator action required to consume the fix).

## ERROR-20260511-6

- timestamp: 2026-05-11T10:45Z (first observed clobber), 2026-05-11T10:53Z (second clobber on NAORISUSDT TP swap)
- mode: FULL_AUTO_LIVE
- symbol: BUSDT (10:45Z), NAORISUSDT (10:53Z)
- attempted_action: other (watcher destructive full-file rewrite)
- binance_code: n/a (race is local; downstream symptom on NAORISUSDT was a -2011 on a cancel-already-cancelled algoId because local state held the pre-swap id)
- binance_message: n/a / "Unknown order sent" (-2011) on the downstream cancel
- internal_state: scripts/watcher.py:289 called ``store.save_all(pos_by_id.values())`` every tick (interval=2s). That code path: (a) loaded the entire positions file once at the top of the tick, (b) mutated only the watcher's own per-tick fields (unrealized_pnl, max_favorable_pnl, max_adverse_pnl) on the in-memory copy, (c) wrote the WHOLE file back. Any concurrent writer (operator-driven SL swap, PnL auto-adjust monitor's TP swap, execution_router post-fill commit, reconciliation script, emergency_close) whose write landed between (a) and (c) was clobbered — their mutated fields silently reverted to the watcher's stale-load value.
- exchange_state: at 10:45Z the new BUSDT SL algoId 3000001507000519 (trigger 0.4514) was placed at Binance and the old SL 3000001506269526 (trigger 0.4264) was cancelled. Watcher write then reverted the local file to the OLD algoId and OLD trigger. Exchange remained correct; only local file was wrong.
- impact: reconciliation_required (twice). On the NAORISUSDT incident the stale local algoId fed back into the next auto-adjust cycle and triggered an HTTP 400 -2011 against an already-cancelled algoId.
- resolution: Three surgical changes — see ERROR-20260511-6-RESOLUTION below.
- escalated_to: error-fix-agent (own the race fix); user (informational).

## ERROR-20260511-6-RESOLUTION

- timestamp: 2026-05-11T11:02:29Z
- mode: code-fix (no live trades issued; watcher kept STOPPED during fix per operator instruction)
- symbol: n/a (systemic fix)
- attempted_action: eliminate watcher's destructive full-file write; replace with locked, whitelisted, per-position merge
- binance_code: n/a
- binance_message: n/a
- internal_state: 5 open positions (BUSDT, LABUSDT, SAGAUSDT, FOLKSUSDT, NAORISUSDT) untouched by the fix; verified bit-identical to pre-fix backup at end of verification.
- exchange_state: binance_position_sync at 11:02:29Z returned sync_status=success, open_positions_count=5, manual_positions_detected=[], state_mismatches=[], new_trades_allowed=true, wallet 29.14791556 USDT, available 10.23347441 USDT.
- impact: blocked_entry (prevents the bug; previous clobber incidents already reconciled manually).
- resolution: Approach A — locked read-modify-write with a tight whitelist. Three surgical changes:
  1. scripts/positions_store.py — added a process-level exclusive file lock (``fcntl.flock`` on ``<path>.lock``) wrapped around every read-modify-write cycle (``save_all``, ``upsert``, ``remove_closed``). Added the new ``apply_watcher_updates(updates)`` method which: (a) takes the lock, (b) re-reads the raw JSON (preserving forward-compat fields like ``planned_loss_at_sl_usdt_initial``), (c) for each position_id in the input, merges ONLY fields in ``WATCHER_ALLOWED_FIELDS`` = {unrealized_pnl, max_favorable_pnl, max_adverse_pnl, updated_at, notes}, (d) ratchets max_favorable_pnl UP only and max_adverse_pnl DOWN only (so a stale tick can never erase an extreme reading from a concurrent writer), (e) skips positions whose on-disk status is no longer "open" with a "skipped:not_open:<status>" outcome, (f) atomic-renames the new file into place. Anything NOT in the whitelist — status, stop_loss, take_profit_targets, algo_order_ids, quantity, exit_price, exit_reason, closed_at — is silently dropped from the input. Also fixed a latent Position.from_jsonable bug: it now silently ignores unknown JSON keys (via ``dataclasses.fields(cls)`` filter) so forward-compat fields like ``planned_loss_at_sl_usdt_initial`` no longer cause ``load_all`` to drop the row.
  2. scripts/watcher.py — removed the destructive ``store.save_all(pos_by_id.values())`` line. The tick now classifies each touched position into one of two persistence routes: (a) NORMAL TICK — diff against an initial snapshot, build a ``{position_id: {whitelisted_field: value}}`` map, flush via ``store.apply_watcher_updates`` at end-of-tick; (b) FULL UPSERT (only two cases) — paper-mode close (pos.status flipped to "closed") OR live-mode trail SUCCESS (apply_decision returned TRAIL_STOP, meaning ``_try_live_trailing`` already cancel-and-replaced the exchange algoOrder so persisting stop_loss + algo_order_ids atomically is now correct). Both routes acquire the file lock through PositionsStore.
  3. tests/test_positions_store.py — added 8 new regression tests covering: stop_loss/algo_order_ids/status are NEVER overwritten by the watcher path; MFE ratchets up only; MAE ratchets down only; concurrent-close survives (skipped:not_open); unknown position_ids return skipped:not_found; forward-compat unknown fields on disk survive a merge; notes are APPENDED not replaced; empty input is a no-op.
- tests: 213 passed, 5 skipped (the existing live-API smoke tests). Previously 205 passed — eight new tests added, zero regressions.
- race_test: PASS. Injected fake BUSDT stop_loss=999.0 + algo_order_ids.sl=FAKE-CONCURRENT-WRITER-ALGO-123. Ran watch_open_positions with a FakeMarket fixture producing close price 0.620 (well above the fake stop). Watcher emitted decision=stop_hit (a sign the fake values were read) but because BUSDT is FULL_AUTO_LIVE, apply_decision was correctly a no-op (the ERROR-20260511-4 fix protecting live-mode local closures). Post-tick file inspection: stop_loss STILL 999.0, algo_order_ids.sl STILL FAKE-CONCURRENT-WRITER-ALGO-123, status STILL "open", closed_at STILL null. unrealized_pnl correctly updated to 3.0348 ((0.620-0.4514)*18), MFE ratcheted 0.6102 -> 3.0348. State then bit-restored from /tmp/open-positions.backup.json so no synthetic-tick data was left on disk.
- field_update_test: PASS. Watcher's allowed fields (unrealized_pnl, max_favorable_pnl, max_adverse_pnl, updated_at, notes) DO update through the new whitelist path. MFE moves up, MAE moves down, uPnL refreshes on every tick. Confirmed all five live positions deserialise cleanly (the from_jsonable filter was needed — every recent live position has planned_loss_at_sl_usdt_initial, which previously caused TypeError-swallowed silent skips in load_all and would have meant the OLD save_all wiped them entirely on next flush).
- post_fix_sync: python3 -m scripts.binance_position_sync at 2026-05-11T11:02:29Z returned sync_status=success, open_positions_count=5, manual_positions_detected=[], state_mismatches=[], new_trades_allowed=true.
- files_changed:
  - /Users/satish/Documents/Claude/Projects/My-Trading-Project/scripts/positions_store.py (file lock + apply_watcher_updates + WATCHER_ALLOWED_FIELDS + from_jsonable forward-compat filter)
  - /Users/satish/Documents/Claude/Projects/My-Trading-Project/scripts/watcher.py (route writes through apply_watcher_updates / per-position upsert; deleted save_all call)
  - /Users/satish/Documents/Claude/Projects/My-Trading-Project/tests/test_positions_store.py (8 new no-clobber regression tests)
- watcher_still_stopped: yes — per operator instruction, the watcher was NOT started after the fix. Operator will restart with python3 -m scripts.run_watch_positions --loop --interval 2 after reviewing this report.
- escalated_to: user (informational — fix landed, watcher safe to restart); safety-agent (informational — the watcher's old class of clobber-driven local/exchange divergence is now structurally impossible).

## ERROR-20260511-7

- timestamp: 2026-05-11T13:10:00Z (observation), 2026-05-11T13:45:00Z (fix landed)
- mode: FULL_AUTO_LIVE
- symbol: n/a (systemic — orchestration gap, not a per-symbol exchange error)
- attempted_action: other (candidate selection / routing — feature gap, NOT a bug per se but tracked here for symmetry with the rest of the cycle-engine fixes)
- binance_code: n/a
- binance_message: n/a
- internal_state: scripts/run_full_auto_cycle.py built its candidate list purely from the Token Screener output (run_screener → top-N by composite score). The user's hand-curated data/watchlist.json — which carries the highest-conviction setups discovered by manual research (e.g. GTCUSDT short-squeeze geometry strengthening across 3 cycles) — was IGNORED by the cycle engine. Result: the cycle kept evaluating off-watchlist screener picks (FOLKSUSDT, ALCHUSDT) first while the user's flagged high-conviction setups (GTCUSDT, USUSDT, INXUSDT) were never seen by the strategy engine. This is an authority inversion: the user's curated conviction should rank ahead of the automated screener's composite score, not behind it.
- exchange_state: n/a — no exchange-side anomaly. Existing open positions (BUSDT, LABUSDT, SAGAUSDT, NAORISUSDT, ALCHUSDT) untouched by this fix.
- impact: cosmetic (no naked exposure, no reconciliation needed) but materially damaging to trading edge — high-conviction watchlist setups were structurally bypassed every cycle.
- resolution: see ERROR-20260511-7-RESOLUTION below.
- escalated_to: user (informational); error-fix-agent (own the implementation).

## ERROR-20260511-7-RESOLUTION

- timestamp: 2026-05-11T13:45:00Z
- mode: code-fix (no live trades issued by this work)
- symbol: n/a (systemic fix)
- attempted_action: add watchlist priority injection to FULL_AUTO_LIVE candidate selection
- binance_code: n/a
- binance_message: n/a
- internal_state: bug fix only; no trade state mutated; 5 open positions untouched.
- exchange_state: unchanged.
- impact: prevents bypass of high-conviction setups; strengthens trading edge without weakening any safety gate.
- resolution: Single-file surgical change in scripts/run_full_auto_cycle.py + one new test file. Three additions:
  1. ``select_watchlist_priority_symbols(watchlist_data, open_position_symbols, now_utc)`` — pure selector. Filters data/watchlist.json entries to ``priority=="high"`` AND ``expires_at > now`` (tolerant of missing field) AND ``side_bias in {"long","short"}`` AND ``symbol not in open_position_symbols``. Preserves file order, dedupes, returns ``list[str]``. Read-only; never mutates the watchlist.
  2. ``_load_watchlist_priority_symbols(open_position_symbols, watchlist_path, now_utc)`` — filesystem wrapper. Returns ``[]`` if the file is absent or corrupt JSON (cycle falls back cleanly to screener).
  3. ``prepend_watchlist_priority(priority_symbols, screener_pairs, specs, ticker_fetcher)`` — builds the final ``(spec, ticker)`` candidate list with watchlist symbols FIRST, screener fallback AFTER. Watchlist symbols already returned by the screener are hoisted (no duplicates). Missing-from-exchangeInfo or ticker-fetch-failure symbols are silently skipped and recorded in a ``skipped`` reporting list so the cycle continues with the remaining priorities and the full screener fallback. Wired into ``main()`` after the screener-pair build and before the proposal loop; emits a single log.info line ``Watchlist priority candidates: [SYM1, SYM2, ...] injected ahead of screener fallback.`` and writes the injected + skipped lists onto report["watchlist_priority"].
- constraint_compliance:
  - Strategy engine's confidence/R:R gates UNCHANGED — priority means "evaluated first", NOT "lower the bar". A failing watchlist symbol still gets rejected by rank_strategies + evaluate_proposal normally, after which the next candidate (a screener fallback) is evaluated.
  - data/watchlist.json is READ-ONLY from this code path — no write, no delete.
  - Already-open symbols excluded from the priority injection (Position.is_open set compared against watchlist symbols at cycle start).
  - .env untouched; no API keys logged or echoed.
  - --i-understand-this-fires-trades-without-asking flag still mandatory; this change does NOT alter the gate.
  - No live order modified by this fix.
- tests: 228 passed, 5 skipped (was 213 passed before). 15 new tests in tests/test_run_full_auto_cycle_watchlist.py covering: file-order preservation, open-position exclusion, expired-entry exclusion (strict <, boundary case), medium/low/neutral filter, missing expires_at handling, malformed input robustness, dedup, file-absent / corrupt-JSON wrapper handling, and the full prepend-ordering scenario the user quoted ([GTC, US, INX, FOLKS, ALCH, ABC] from priority=[GTC, US, INX] + screener=[FOLKS, ALCH, ABC]).
- files_changed:
  - /Users/satish/Documents/Claude/Projects/My-Trading-Project/scripts/run_full_auto_cycle.py (added selector + filesystem wrapper + prepend helper; wired into the screener-path candidate build; report["watchlist_priority"] surfaces injected + skipped lists; log line on injection)
  - /Users/satish/Documents/Claude/Projects/My-Trading-Project/tests/test_run_full_auto_cycle_watchlist.py (new — 15 tests)
- escalated_to: user (informational — fix landed, next FULL_AUTO_LIVE cycle will evaluate watchlist symbols first); safety-agent (informational — no safety gate touched; bypass behaviour was strictly degrading edge, not relaxing protection).

## ERROR-20260511-8: clientAlgoId duplicate on same-symbol same-day retry
- 2026-05-11T16:46:52Z
- Symbol: BILLUSDT (3rd attempt today). Earlier attempts: 16:11Z (filled, SL hit, position closed), 16:23Z (margin insufficient, no fill), 16:46Z (entry fill ok, TP placement -4116 ClientOrderId duplicated → naked-entry-rescue closed).
- Root cause: clientAlgoId pattern `TP-PROP-<YYYYMMDD>-<SYMBOL>-001` is fixed per symbol-day. Same-day re-entries trigger -4116 duplicate.
- Fix needed: append a per-attempt counter or millisecond suffix to clientAlgoId. Same fix for SL clientAlgoId.
- Today's net impact: BILL ledger = -0.45 (16:17 SL hit) + ~0.003 (16:46 rescue close) = -0.45. The rescue worked correctly — no naked position.
- Workaround: avoid BILL for remainder of session today.

## FIX SHIPPED 2026-05-11T~18:15Z — ERROR-20260511-8
- file: scripts/execution_router.py
  - lines 19–25 (imports): added `import time`.
  - lines 440–456 (in `_place_brackets_or_rescue`): replaced fixed `f"SL-{proposal_id}"[:36]` / `f"TP-{proposal_id}"[:36]` clientAlgoIds with calls to `_build_algo_client_id("SL", proposal_id)` / `_build_algo_client_id("TP", proposal_id)`.
  - lines 670–700 (module footer): added `_build_algo_client_id(role, proposal_id)` helper. Pattern: `<ROLE>-<proposal_truncated>-<ms6>` where `ms6 = int(time.time()*1000) % 1_000_000`. Guaranteed ≤ 36 chars (Binance cap); suffix always preserved so retries differ even when proposal_id is long enough to be truncated.
- file: tests/test_execution_router.py
  - lines 13–17 (imports): imported `_build_algo_client_id`.
  - end of file: two new tests — `test_build_algo_client_id_back_to_back_calls_differ` (asserts millisecond-boundary uniqueness with a 2ms sleep) and `test_build_algo_client_id_respects_binance_36_char_limit` (asserts ≤36-char cap and suffix-preservation under truncation).
- verification: `pytest tests/ -q` → 234 passed, 5 skipped (was 228/5; 6 new tests added across both fixes, zero regressions).
- behaviour change: zero — only impacts the algoOrder clientAlgoId string. Trade decisions, sizing, risk gates, and order semantics are untouched.

## ERROR-20260511-9: Non-ASCII symbol "币安人生USDT" leaked to API; -1100 illegal characters
- 2026-05-11T17:01:36Z
- Symbol seen in request: `%E5%B8%81%E5%AE%89%E4%BA%BA%E7%94%9FUSDT` = "币安人生USDT" (Binance Life USDT display name)
- Cycle context: engine attempted 2 fires this cycle. First (UBUSDT) filled successfully at 0.15246 BUT cycle CRASHED on second proposal due to non-ASCII symbol → newClientOrderId fails Binance regex `^[.A-Z:/a-z0-9_-]{1,36}$`
- Root cause: screener returned a token whose Binance display name (cn_name field) leaked into the actual symbol field. Probable upstream: `scripts/token_screener.py` or `scripts/strategy_engine.py` reading wrong field from /fapi/v1/exchangeInfo.
- Side-effect: UBUSDT was filled but brackets were never placed by execution_router (crashed before). Manual reconciliation: SL 0.14413, TP 0.16913 placed via direct API call at 17:02Z.
- Fix needed: add `re.match(r'^[A-Z0-9]+USDT$', symbol)` guard in screener output AND in engine pre-flight check.
- Workaround: none — cycle will crash again if engine picks same symbol.

## FIX SHIPPED 2026-05-11T~18:15Z — ERROR-20260511-9
- file: scripts/symbol_filters.py
  - lines 19–43 (imports + module header): added `import logging`, `import re`, `log = logging.getLogger(__name__)`, the `ASCII_USDT_SYMBOL_RE = re.compile(r"^[A-Z0-9]+USDT$")` regex, and the `is_valid_ascii_usdt_symbol(symbol)` predicate.
  - lines ~163–177 (in `parse_exchange_info`): after `parse_symbol_spec` succeeds, drop the spec if `is_valid_ascii_usdt_symbol(spec.symbol)` is False. Emit a `[NON_ASCII_SYMBOL_DROPPED]` WARNING log line and continue. This is the earliest funnel: the screener (`scripts/token_screener.py:run_screener`), `scripts/run_full_auto_cycle.py` (both `--symbol` and screener paths), and every other consumer all build their symbol universe from `parse_exchange_info(...)`, so the bad symbol can no longer reach downstream code.
  - lines ~298–303 (`__all__`): exported `is_valid_ascii_usdt_symbol` and `ASCII_USDT_SYMBOL_RE`.
- file: scripts/execution_router.py
  - line 38 (imports): imported `is_valid_ascii_usdt_symbol`.
  - lines 355–369 (top of `_fill_live`): added a belt-and-suspenders ASCII check immediately before any live API call. If a caller bypasses the screener (e.g. via `--symbol`), the router still rejects with reason `"non-ASCII symbol rejected by router guard: ..."` and logs `[NON_ASCII_SYMBOL_DROPPED]`.
- file: tests/test_symbol_filters.py
  - imports: added `is_valid_ascii_usdt_symbol`, `parse_exchange_info`.
  - 4 new tests: `test_ascii_symbol_guard_accepts_normal_symbols` (BTCUSDT, DOGEUSDT, 1000PEPEUSDT), `test_ascii_symbol_guard_rejects_non_ascii_display_name` (exact "币安人生USDT" symbol from this incident), `test_ascii_symbol_guard_rejects_lowercase_and_non_usdt` (negative cases: lowercase, BUSD quote, empty, dash, None), `test_parse_exchange_info_drops_non_ascii_symbol` (end-to-end — feeds a mixed exchangeInfo payload with one bad + one good symbol and asserts only the good one survives).
- verification: `pytest tests/ -q` → 234 passed, 5 skipped. No non-ASCII symbol can now reach the router, the algo-order placement, or the live entry call.
- behaviour change: zero on legitimate symbols — every Binance USDT-M perp ticker matches `^[A-Z0-9]+USDT$`. The only thing that changes is that display-name leakage is now dropped instead of crashing the cycle.
