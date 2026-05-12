# Learning Insights

Recommendations from the Learning & Optimization Agent. Format follows `agency/learning-policy.md`.

## Pending User Approval

## INSIGHT-20260512T-HOLD-DURATION-EDGE-CURVE

- insight_id: INSIGHT-20260512T-HOLD-DURATION-EDGE-CURVE
- category: exit-timing / strategy-edge-decay
- status: PROPOSED (measurement-only; no live-risk change)
- observation: First-ever pass at bucketing the 42 closed positions in `data/open-positions.json` by `closed_at − opened_at` hold duration vs realized PnL. Result is a clearly non-monotonic edge curve:

    | hold bucket | n | win% | sum_pnl | avg_pnl |
    | --- | --- | --- | --- | --- |
    | 0–15m   | 6  | 16.7% | -1.717 | -0.286 |
    | 15–30m  | 10 | 60.0% | +4.197 | +0.420 |
    | 30–60m  | 6  | 66.7% | +2.137 | +0.356 |
    | 60–120m | 10 | 20.0% | +1.866 | +0.187 |
    | 120–240m| 7  | 71.4% | +2.085 | +0.298 |
    | 240m+   | 3  | 33.3% | +0.203 | +0.068 |

    Two striking patterns: (1) the **0–15m bucket is the only net-negative bucket** (-1.72 USDT total, 16.7% win-rate) — these are almost certainly SL-hits / instant invalidations / noise stop-outs and represent the *worst* edge, suggesting min-hold-time gating or wider initial SL on the first 15m is worth measuring. (2) The **60–120m bucket has 20% win-rate but is still net-positive** (+1.87 USDT) — winners in that band are large enough to carry many losers, which is the inverse of the 0–15m bucket. (3) 240m+ degrades sharply (avg +0.07 USDT), consistent with edge-decay on small-cap scalps.
- evidence_window: closed-position snapshot 2026-05-12, n=42 — small-n caveat, but the 0–15m signal is the strongest in the dataset (worst win%, worst sum, worst avg, all aligned).
- failure_mode_if_ignored: agency continues to take 0–15m exits whose loss-rate (83%) is **5× higher** than the 30–60m bucket's loss-rate (33%). Per CLAUDE.md user verbatim "*skip getting lose*" and the new 0.10 USDT max-loss cap, sub-15m losers are the dominant leakage source and they are currently invisible — no metric, no journal field, no alert tracks "how long did this trade live before it died." All other queued items (R-trail, giveback, reconciler, etc.) operate at runtime *during* the position; none diagnose duration-vs-outcome *after* close.
- proposed_change (MEASUREMENT-ONLY, no behaviour change):
    - **PART A:** add a `hold_minutes` computed field to each row appended to `memory/trade-journal.md` (or to a new `data/trade-outcomes.jsonl`) when a position closes, plus a daily rollup line `{date, n_total, n_sub15m, sub15m_winrate, sub15m_pnl, 30_60m_winrate, 30_60m_pnl}`. Read-only; uses existing `opened_at` / `closed_at`. Zero order touch.
    - **PART B (after 14 days of PART A data, n ≥ 100):** if sub-15m bucket remains net-negative with win-rate ≤ 25%, surface a separate INSIGHT recommending a **diagnostic gate** (logging only, not blocking) that flags trades closing in < 15 minutes for post-mortem — was it SL noise? Was it a giveback exit? Was it a manual close? Categorising the sub-15m losers is the precondition for any future rule change.
- measurement_plan: 14-day window post-ship. Success = sub-15m bucket either (a) statistically confirms as a loss generator at n ≥ 30 (greenlights PART B), or (b) regresses to mean / improves (closes the insight). Either is informative.
- expected_impact: zero direct PnL impact (metric only). Indirect ceiling: if sub-15m losses (-1.72 USDT over ~24h of trading) were eliminated entirely on a future rule, daily PnL improvement ≈ +1.7 USDT/day on 30-USDT wallet ≈ +5.7%/day — material but speculative until PART B's root-cause work runs.
- risk_of_change: nil. Read-only computation on already-stored timestamps.
- approval_needed_from: user (acknowledge measurement-only) → ship PART A.
- depends_on: none.
- not_duplicative_check: queued list explicitly excludes hour-of-day; this is *duration*, not *time-of-day*. Distinct from "time since last trade" (which is gap between trades, not lifetime of a trade). Distinct from trapped-PnL insight (which measures live unrealized state, not post-close outcome). Distinct from R-trail/giveback (those are runtime rules; this is post-mortem distribution analysis). No prior INSIGHT bucketizes outcomes by hold duration.


## INSIGHT-20260512T-TRAPPED-PNL-NO-SL-ON-WINNERS

- insight_id: INSIGHT-20260512T-TRAPPED-PNL-NO-SL-ON-WINNERS
- category: exit-discipline / unrealized-pnl-protection
- status: PROPOSED (measurement-mode; surfaces missing protection on live winners)
- observation: Sampled live open book (48 positions, 6 with uPnL > 0). Computed two metrics never tracked before — **TRAPPED PnL** (uPnL > 0 on positions whose SL is still adverse-side of breakeven, i.e. the entire current gain can revert to a loss without any cap) and **GIVEBACK** (sum of MFE − uPnL across the book, i.e. unrealized profit the book has already surrendered while still open). Findings:
    - total uPnL = +6.14 USDT, total MFE-to-date = +30.58 USDT → **giveback so far = 24.07 USDT** (78.7% of peak unrealized profit has already evaporated while the positions remain open).
    - 6/6 winners (100%) have `stop_loss = None`. Locked PnL = 0.00. Trapped PnL = 7.93 USDT.
    - r_at_peak distribution for the 6 winners: 42.4R, 31.7R, 13.7R, 6.3R, 5.7R, 3.0R. Per CLAUDE.md auto-trail rule, **every one of these should have been moved to at least breakeven at ≥ 0.9R and to lock ≥ +1.5R by now**. None have been.
    - This is independent from already-queued items: not the trail-rule design itself (R-trail is queued separately and is about *defining* the ladder), not run_close_position (about close-side tooling), not the watcher cross-verify (about staleness). This is the **measurement layer**: there is no metric, log line, or alert anywhere that surfaces "winners on the book with no protective SL" — so the auto-trail rule's non-application has been silently invisible.
- evidence_window: live snapshot 2026-05-12, n=48 open / n=6 winners; one snapshot only — small-n, but the 0/6 protection rate combined with the documented 24.07 USDT giveback already locked-out is a strong directional signal.
- failure_mode_if_ignored: CLAUDE.md aggressive-scalp policy (hard cap at +2.0 USDT, MFE giveback rules) and the R-trail ladder both depend on protective SLs actually being placed and trailed. Without a measurement surface, the agency cannot tell whether the trail cron is (a) not running, (b) running but failing silently, or (c) running but skipping winners due to a bug. The 42R-peak / SL=None / 21% of peak retained pattern points to scenario (a) or (b). Continued state means user's verbatim mandate "*we want profits not the losses*" is structurally unmet on the live book.
- proposed_change (TWO-PART, both MEASUREMENT-ONLY — no behaviour change, fully reversible):
    - **PART A (instant, code-only, low-risk):** add three computed fields to the next `data/pnl-snapshots.jsonl` writer pass — `trapped_pnl_usdt` (sum of uPnL on winners with SL adverse of BE or SL=None), `locked_pnl_usdt` (sum on winners with SL ≥ BE for LONG / ≤ BE for SHORT), `giveback_unrealized_usdt` (Σ max(0, MFE − uPnL)). Emits a single new daily JSON line. No order placement, no SL modification. Surfaces the gap so the existing R-trail / giveback rules can be debugged against ground truth.
    - **PART B (after one week of PART A data):** add an audit cron that compares each winner's `r_at_peak` to the CLAUDE.md auto-trail ladder and logs (does NOT execute) a "WOULD-TRAIL" diagnostic line per snapshot. If across a 7-day window ≥ 70% of winners with r_at_peak ≥ 0.9R show `stop_loss = None`, escalate as a separate INSIGHT recommending root-cause investigation of the trail-cron itself. Still no live-risk increase.
- measurement_plan: after PART A ships, run for 7 days. Success = trapped_pnl_usdt / (trapped_pnl_usdt + locked_pnl_usdt) trends DOWN as the R-trail cron starts firing (or as PART B exposes that it never fires). Either outcome is informative.
- expected_impact: zero direct PnL impact (this is a metric, not a rule). Indirect: if today's pattern holds (≈ 78% giveback rate), and the R-trail rule is eventually enforced after PART B's diagnosis, recovering even 30% of the 24 USDT/day giveback would equal ≈ 7 USDT/day on a 30-USDT wallet — material.
- risk_of_change: nil for PART A (read-only metrics from existing position state). Nil for PART B (logging only, no order touch).
- approval_needed_from: user (acknowledge measurement-only nature) → Risk Manager (confirms no live-risk change) → ship PART A.
- depends_on: none. **Distinct from** R-trail queued item (this measures whether R-trail is even running), distinct from giveback-protection queued items (those exit; this protects), distinct from reconciler write-back (different subsystem).
- not_duplicative_check: searched memory for `trapped|giveback.{0,15}metric|unprotected.{0,15}winner|sl.{0,5}=.{0,5}none.*audit` — no prior INSIGHT covers this measurement layer; closest neighbours (INSIGHT-20260511-009 giveback-protection tier-gap, INSIGHT-2026-05-12T04:05Z pause-state SLA) operate on different signals.



- insight_id: INSIGHT-20260512-001
- category: risk / portfolio-construction
- observation: The Risk Manager and `scripts/limits.py` enforce per-trade caps (margin, leverage, max-loss), per-cycle caps (trade-cap=2), and global caps (max-open=8, no-duplicate-symbol). **There is NO portfolio-level directional-concentration cap.** A grep across `scripts/` and `agents/risk-manager-agent/` for `directional|concentration|net_delta|same_side|book_imbalance` returns only `strategy_scoring.py` (a single-trade directional-momentum reference, unrelated to book-level exposure). Current open book confirms the gap: **48 open positions** (note: this materially exceeds the user-locked max-open=8 — flagged separately under INSIGHT-MAX-OPEN-DRIFT; here the relevant fact is just the count for sample-size purposes), split **29 LONG / 19 SHORT** (60.4% LONG, net +10 directional units). The skew today happened to align with btc_flat_alt_rotation regime, but the system has no governor preventing 48 LONG / 0 SHORT or vice-versa under a regime miscall. A single BTC -3% move with a heavily LONG-skewed book would breach the 4.0 USDT daily-loss cap before per-trade SLs trigger sequentially — the SL-per-trade design assumes uncorrelated outcomes, which is false in a correlated alt-coin book.
- evidence:
    sample_size: 48 open positions (snapshot 2026-05-12), 25 unique symbols
    win_rate: not the relevant metric; this is a tail-risk / correlation-clustering observation
    avg_pnl: n/a — pre-event design gap
    regime: btc_flat_alt_rotation; risk is highest in regime *transitions*, which is exactly when the gate would matter most
- recommended_change: Add a **read-only metric + soft-warn** in this first iteration (no hard block yet, per "never increase live risk automatically" — but a *cap on new entries on the over-weighted side* is RISK-REDUCING and so qualifies for the safer direction). Concretely:
    1. Add `scripts/book_concentration.py` with a pure function `compute_directional_imbalance(open_positions) -> {longs:int, shorts:int, ratio:float, net_notional_usdt:float, dominant_side:str|None}`.
    2. Add a config knob `BOOK_DIRECTIONAL_IMBALANCE_THRESHOLD` (default **0.70**, i.e. soft-warn when one side >= 70% of open count; user can tune). Read from env / `agency/limits.yaml`.
    3. In `risk-manager-agent` pre-approval flow, compute current ratio. If approving the proposed trade would push the dominant side to >= threshold, **EMIT WARNING + REQUIRE explicit reason field in approval JSON** (`directional_concentration_acknowledged: true`). Do not auto-block in v1 — let the user/orchestrator decide. v2 can promote to hard-block after observation.
    4. Add a journal field `book_imbalance_at_entry` written on every fill, so the Learning agent can correlate skew with drawdown days statistically before any risk-tightening is recommended.
    5. Six unit tests: empty book, single-side, balanced, threshold-just-below, threshold-just-at, threshold-just-above.
- requires_user_approval: true (introduces a new gate, even if soft, on the live-approval path; also touches the approval JSON schema)
- safety_impact: low — direction is risk-REDUCING (warn before lopsided books), no change to per-trade caps, no leverage/margin/max-loss/daily-cap touched. The threshold default 0.70 is conservative-loose to avoid false positives in the early observation period.
- created_at: 2026-05-12T00:00:00Z
- status: pending_user_approval

## INSIGHT-20260511-001

- insight_id: INSIGHT-20260511-001
- category: execution
- observation: The strategy/risk engine's single-TP fallback (triggered every cycle on this wallet because the 33/33/33 scale-out fails MIN_NOTIONAL on all small-cap symbols) places the TP at the TP1 level, producing an initial R:R of 1.43-1.85 on every trade and violating the locked-policy R:R >= 2.0 floor at the moment of entry. The watcher's AUTO_TP_TO_TP2 rule compensates 5-19 minutes after entry by cancel-and-replace at TP2 (R:R ~2.5). Pattern is recurring and matches the user's pending-bug note ("ERROR-20260511-6-style engine bug — single-TP fallback uses TP1 instead of TP2 (compensated by auto-adjust monitor but engine still wrong)").
- evidence:
    sample_size: 12 closed trades today, 7 of them carried the AUTO_TP_TO_TP2 watcher note (58%); all 7 had engine R:R in [1.43, 1.85] vs locked-policy floor 2.0
    win_rate: 58.3% overall today (7W/5L); within the 7 promoted trades: 4W/3L (FOLKS/GTC/TRUTH/SAGA1 wins; LAB/VVV/US losses, ALCH research exit)
    avg_pnl: +0.197 USDT per closed trade today; +2.366 USDT total
    regime: btc_flat_alt_rotation, BTC +0.4-0.5%/24h
- recommended_change: Fix the strategy/risk engine's single-TP fallback to select TP2 (R:R target 2.5) instead of TP1 (R:R target 1.5) when the 33/33/33 split is infeasible and >= 2 TP targets are available. This is a code-fix, not a risk-rule change — the locked R:R >= 2.0 floor is unchanged; we are merely correcting the engine's compliance with it at moment of entry. Likely site: scripts/strategy_engine.py or scripts/risk_engine.py where take_profit_targets is collapsed to a single value. Add a unit test asserting R:R >= 2.0 on the chosen TP when len(tps) >= 2.
- requires_user_approval: false (code-fix, non-risk-changing; auto-executable per agency/learning-policy.md "Spawn error-fix-agent for non-risk-changing code improvements")
- safety_impact: low (closes a 5-19 min latent sub-policy R:R window; no risk parameters changed; no leverage/margin/max-loss touched)
- created_at: 2026-05-11T14:50:00Z
- status: pending

## INSIGHT-20260511-003

- insight_id: INSIGHT-20260511-003
- category: exit
- observation: The locked-policy aggressive scalp-exit rules (USDT-threshold MFE/pullback table in CLAUDE.md — "MFE>=1.0 exit on pullback>=0.25", "MFE>=0.50 exit on pullback>=0.15", "MFE>=0.30 exit if 80% gave back", "hard cap close at uPnL +2.0") are not encoded in any Python module. scripts/profit_protection.py only implements the older percentage-of-MFE rules (50%/75%). The newer USDT-threshold rules are executed each watch cycle by the orchestrator agent reading CLAUDE.md and manually firing a reduce-only MARKET close. This worked today (4 of 12 closes today fired by this rule, capturing ~+1.03 USDT of the day's +2.34 USDT realized = ~44% of P&L), but the structural fragility is real: cron skip, prompt drift, or orchestrator stall would silently disable a rule that today drove half of session profit. There are also no unit tests asserting deterministic behavior, no journal-row trail of "checked, did not fire" evaluations, and no recovery path if the rule miscarries.
- evidence:
    sample_size: 4 MFE_PULLBACK_EXIT fires in 12 closed trades today (TRUTHUSDT MFE 0.87 pullback 0.19 -> +0.68; NAORISUSDT MFE 0.66 pullback 0.26 -> +0.39; SAGAUSDT-1 MFE 0.59 pullback >0.50 -> +0.09; QUSDT MFE 0.31 giveback 80%+ -> -0.13). Fire-rate 33% of closed trades.
    win_rate: 3W/1L on the 4 rule-fires (the 1L was the giveback-preventive QUSDT close which still saved ~0.37 USDT vs full SL trigger)
    avg_pnl: +0.258 USDT per fire (sum +1.03 USDT)
    regime: btc_flat_alt_rotation, BTC stable
- recommended_change: Encode the aggressive USDT-threshold scalp-exit rules into scripts/profit_protection.py (or a new scripts/aggressive_scalp_exit.py module), wired into the watcher loop ahead of the existing profit_protection.advise() call. Add a frozen dataclass AggressiveScalpExitConfig mirroring the CLAUDE.md table verbatim, a pure should_aggressive_scalp_exit(pos) -> (bool, reason) function, and at least 6 unit tests covering each threshold-tier boundary (just-below, just-at, just-above for each of MFE>=1.0/0.50/0.30 and the +2.0 hard-cap). Add a journal entry "scalp_exit_check" emitted every watcher tick (fire or no-fire) for observability. NO change to leverage, margin, max-loss, daily-cap, max-open, R:R floor — risk parameters fully preserved. Only the EXIT rule transitions from LLM-mediated to deterministic.
- requires_user_approval: true (changes the live-exit decision path from LLM-mediated to deterministic; even though the rule itself is unchanged, the execution mechanism is new code on a high-stakes path)
- safety_impact: low to medium — the encoded rule is the same rule the orchestrator currently executes manually, so the rule's expected behavior is identical. The risk is implementation bugs (e.g., off-by-one threshold, wrong sign on uPnL for SHORTs). Unit-test coverage mitigates this. Once shipped, the system is safer because the rule cannot silently fail to fire from a missed cron or stale prompt.
- created_at: 2026-05-11T14:55:00Z
- status: pending_user_approval

## INSIGHT-20260511-002

- insight_id: INSIGHT-20260511-002
- category: strategy
- observation: LONG-vs-SHORT win-rate split in today's btc_flat_alt_rotation regime: LONG 6W/3L = 66.7% WR / +2.39 USDT (n=9); SHORT 1W/2L = 33.3% WR / -0.04 USDT (n=3). All three SHORTs (LABUSDT, NAORISUSDT, QUSDT) reached MAE >= MFE before resolving; only NAORISUSDT printed net positive. Same-side longs in alt-rotation regimes consistently captured larger MFE distributions (mean MFE for LONG winners: 0.91 USDT; for SHORT winner: 0.66 USDT).
- evidence:
    sample_size: 12 closed trades today (9 LONG, 3 SHORT) — BELOW the 20-sample statistical floor required by agency/learning-policy.md
    win_rate: LONG 66.7%, SHORT 33.3%
    avg_pnl: LONG +0.266 USDT/trade, SHORT -0.013 USDT/trade
    regime: btc_flat_alt_rotation
- recommended_change: NO RULE CHANGE YET — sample too small. Monitor for next 20+ trades in the same regime. If the pattern holds (SHORT WR < 40% AND SHORT avg PnL <= 0 across 20+ samples), propose a regime-conditional confidence-tier penalty on SHORT setups during btc_flat_alt_rotation (e.g., subtract 0.05 from confidence for SHORT proposals in this regime, which pushes them down a leverage tier). Do NOT propose blocking SHORTs entirely — the sample is too small and one strategy_pullback_short loss (LABUSDT) is not statistically significant.
- requires_user_approval: true (any side-bias rule must be explicitly user-approved)
- safety_impact: none (would only tighten the screening filter, not raise risk)
- created_at: 2026-05-11T14:50:00Z
- status: pending_more_data



```
## INSIGHT-YYYYMMDD-N

- insight_id:
- category: screening | strategy | risk | execution | exit | reporting
- observation:
- evidence:
    sample_size:
    win_rate:
    avg_pnl:
    regime:
- recommended_change:
- requires_user_approval: true
- safety_impact: none | low | medium | high
- created_at:
- status: pending | approved | rejected | superseded
```

## INSIGHT-20260510-001

- insight_id: INSIGHT-20260510-001
- category: risk
- observation: All signal-generating proposals in today's cycle were rejected by the Risk Manager because the MIN_NOTIONAL requirement (5 USDT) forced minimum quantities (38 UBUSDT, 12 币安人生USDT) that produced stop-loss loss amounts (0.12-0.19 USDT) exceeding the max_planned_loss per trade (0.05 USDT at 5% of 1 USDT margin). The stop distances (~2.2-3.7%) are structurally correct for these volatile tokens but are too wide for a sub-2 USDT margin account on MIN_NOTIONAL-constrained symbols.
- evidence:
    sample_size: 2 signals (UBUSDT short_after_pump, 币安人生USDT short_after_pump)
    win_rate: N/A (no trades placed)
    avg_pnl: N/A
    regime: volatile small-cap pump environment
- recommended_change: Consider either (1) increasing max_margin_per_trade_usdt from 2 to 3-4 USDT if wallet allows, which would allow a proportionally larger max_loss (0.15-0.20 USDT at 5%) and pass the MIN_NOTIONAL constraint; or (2) adding a screener filter to exclude symbols with MIN_NOTIONAL >= 5 USDT when wallet is very small; or (3) raising max_planned_loss_per_trade to 8-10% of margin (from 5%) to accommodate wider stops on volatile tokens, with user approval.
- requires_user_approval: true
- safety_impact: medium (changing max_loss rule directly affects capital protection)
- created_at: 2026-05-10T16:34:00Z
- status: pending

## INSIGHT-20260510-002

- insight_id: INSIGHT-20260510-002
- category: screening
- observation: The Binance production API is geo-restricted from this server environment (HTTP 451). All market data and screener operations must route through Binance testnet (testnet.binancefuture.com) when running from this server. The testnet has 705 symbols available including realistic price data. The BinanceClient defaults to production and does not read BINANCE_TESTNET env var automatically.
- evidence:
    sample_size: 1 cycle (2026-05-10)
    win_rate: N/A
    avg_pnl: N/A
    regime: N/A
- recommended_change: Update scripts/binance_client.py to auto-read BINANCE_TESTNET env var in __init__ and set base_url to TESTNET_BASE when true. This avoids the manual monkey-patch workaround needed to run paper cycles from this environment.
- requires_user_approval: false
- safety_impact: low (paper trading only; testnet data is realistic for paper cycle purposes)
- created_at: 2026-05-10T16:34:00Z
- status: pending

## Approved Changes (Active)

<!-- Insights the user accepted. Rule changes are reflected in the relevant agency/*.md files. -->

## Rejected Insights

<!-- Insights the user declined; do not re-propose without new evidence. -->

## Superseded Insights

<!-- Insights replaced by later, better evidence. -->

## INSIGHT-20260511-004

- insight_id: INSIGHT-20260511-004
- category: execution
- observation: The trade-journal has no deterministic close-event writer. ``scripts/journal_writer.py::append_paper_trade`` writes structured entry blocks at trade-OPEN time only. All ``## TRADE-CLOSE-2026-05-11T*`` close rows in memory/trade-journal.md are hand-typed by the orchestrator LLM (confirmed: ``grep -r "TRADE-CLOSE-" scripts/`` returns ZERO matches). Result: data-integrity drift (LABUSDT close row at 11:43:53Z says qty=5 realized=-1.32 vs the authoritative position record's qty=2 realized=-0.30 — off by 4x and uncorrected 5+ hours later), schema drift (10+ ad-hoc exit_reason strings observed today vs the 7-value enum documented in append_paper_trade's docstring), no machine-parseable realized_pnl aggregation possible.
- evidence:
    sample_size: 14 (close rows today, n=1 confirmed-wrong)
    win_rate: 0.50
    avg_pnl: 0.167
    regime: btc_flat_alt_rotation full_auto_live
- recommended_change: Add scripts/journal_writer.py::append_close_event(position_record, exit_reason_enum, realized_pnl_usdt, fees_usdt, exit_order_id) — a deterministic close-event writer consuming the closed Position dataclass + exchange exit metadata. Constrained exit_reason enum: tp_hit | partial_tp | sl_hit | breakeven_lock | mfe_pullback_exit | giveback_protection | loss_research_exit | trail_exit | emergency_exit | manual. Idempotent (refuse duplicate trade_id). Wire into the watcher exit-execution path so each close atomically marks the position closed AND emits the structured row. Ship alongside one-shot ``scripts/reconcile_journal.py --fix-stale-rows`` retroactive cleanup tool to correct LABUSDT-style errors.
- requires_user_approval: true
- safety_impact: none (audit-trail only — no risk param touched, no order modified, no live-fire path affected)
- created_at: 2026-05-11T16:00:00Z
- status: pending_user_approval

## INSIGHT-20260511-005

- insight_id: INSIGHT-20260511-005
- category: execution / strategy
- observation: scripts/strategy_scoring.py::_momentum_continuation (lines 401-449) sets entry_zone = (last * 0.998, last * 1.002) — a 0.4%-wide MARKET-equivalent band — and does NOT consume r.structure.pct_from_24h_high / pct_from_24h_low to compute range-position (rngpos). The only no-chase guard is the opaque boolean r.structure.is_overextended_long/short which applies a -0.20 confidence penalty, not a hard reject. Result: tokens at rngpos >= 0.85 (local 24h high) trigger momentum_continuation LONG and fire MARKET at the extreme, structurally unable to honor discovery's "wait for pullback" caveat. Today's two upper-rngpos LONG chases (BILLUSDT ~94%, UBUSDT ~90%) hit loss (-0.454 and currently -0.31R); two mid-range LONGs (SAGAUSDT ~68%, TRUTHUSDT mid) won (+0.444 and +0.681).
- evidence:
    sample_size: 4 (today's momentum_continuation fires)
    win_rate_rngpos_ge_0_85: 0.00 (0/2)
    win_rate_rngpos_lt_0_75: 1.00 (2/2)
    regime: btc_flat_alt_rotation full_auto_live
    code_location: scripts/strategy_scoring.py:401-449
    mechanism_confirmed: yes (code-read, not just outcome-inferred)
- recommended_change: In _momentum_continuation, compute rngpos from pct_from_24h_high/low. Hard-reject when rngpos >= 0.85 (LONG) or <= 0.15 (SHORT) with cons=["rngpos extreme — wait for pullback"]. For 0.75-0.85 LONG (resp 0.15-0.25 SHORT), widen entry_zone to the mid-range band (e.g., day_low + 0.50*range to day_low + 0.75*range) so engine emits a LIMIT pullback order instead of a MARKET chase. Surface rngpos in pros/cons for journal audit. NO risk-parameter change; this is strategy-engine input-completeness.
- requires_user_approval: true
- safety_impact: none (strictly reduces fires at extremes; never adds risk or widens stops)
- created_at: 2026-05-11T16:25:00Z
- status: pending_user_approval

## INSIGHT-20260511-008

- insight_id: INSIGHT-20260511-008
- category: observability / audit
- observation: data/loss-research-log.jsonl is hand-typed by the orchestrator LLM each cycle (verified — no script in scripts/ writes the file). Today (n=14 decisions, 5 EXIT_EARLY, 9 HOLD) all 5 EXIT_EARLY fires were correct ex-post (avoided SL hits, saved estimated +1.72 USDT vs hold-to-SL), and all 9 HOLD decisions converted to losses or eventual EXIT_EARLY (zero converted to profit). However, the log MISSES the structured fields needed to validate the rule statistically over 20+ decisions: sl_price_at_decision, entry_price_at_decision, position_id (for JOIN to data/open-positions.json), decision_outcome_post_close (retroactively filled), and hold_followup_decision_id (to chain HOLD→re-eval→EXIT sequences). Without these the loss-research-agent's effectiveness is asserted, not measured; the 100% EXIT_EARLY success rate is currently unfalsifiable.
- evidence:
    sample_size: 14 (today's loss-research decisions)
    exit_early_count: 5
    hold_count: 9
    exit_early_correctness_rate: 1.00 (5/5, but unfalsifiable without structured fields)
    hold_to_profit_rate: 0.00 (0/9 converted to profit; all became EXIT_EARLY or SL)
    estimated_saved_vs_sl: +1.72 USDT (eyeballed from journal context)
    side_bias: all 14 decisions were SHORT-side positions (selection bias flag)
    file_writer_exists: no (grep -r "loss-research-log" scripts/ returns 0 matches)
- recommended_change: Add scripts/loss_research_logger.py with append_decision(position_id, symbol, r_curr, decision, reasoning, confidence, sl_price, entry_price) using fcntl.flock for atomic writes. Add reconcile_decision(position_id) called by close-event writer to retroactively populate decision_outcome_post_close. One-shot retroactive enrichment script to backfill today's 14 rows with sl_price/entry_price from data/open-positions.json. Wire into orchestrator so every cycle calling token-research-agent on r_curr <= -0.3R uses this writer. NO risk-parameter change; pure observability fix.
- requires_user_approval: true
- safety_impact: none (audit-trail / efficacy-measurement layer; never modifies which positions close, when, or how)
- created_at: 2026-05-11T17:20:00Z
- status: pending_user_approval
- depends_on: INSIGHT-20260511-004 (close-event writer must define position-record schema before reconcile_decision can JOIN against it)


### INSIGHT-20260511-009 — Giveback-protection "stuck-between-tiers" gap (MFE 0.20-0.30)
- **Status:** pending_user_approval
- **Safety impact:** none — exit-only behaviour, never raises live risk
- **Sample size:** n=1 (HUSDT-2 today, MFE +0.25 → +0.02, 92% giveback, zero protection fired)
- **Confidence:** low (single observation)
- **Recommendation:** Add tier `MFE ≥ 0.20 AND uPnL ≤ MFE × 0.30` → reduce-only MARKET close. Ship in measurement-mode for 24-48h before activating.
- **Statistical caveat:** below 5-observation threshold from `agency/learning-policy.md`. Ship-as-measurement only.
- **See:** `memory/system-improvements.md` ENH-2026-05-11T17:30Z for full rationale.


### INSIGHT-20260511-010 — Loss-research HOLD on positions <10min old recovered 0/3 today (FOMO-entry trap)
- **Status:** pending_user_approval
- **Safety impact:** none — exit-only behaviour, never raises live risk; only changes default decision for a narrow age-conditional cohort
- **Sample size:** n=2 confirmed (UBUSDT 1min/HOLD/-0.295; BILLUSDT 1min/HOLD/-0.454) + n=1 inferred (ALCH-re-entry SL hit without ever being researched) = 3/3 SL hits on young chase-entries today
- **Confidence:** medium (mechanism identified — young + never-green = no mean to revert to — but n below 20-sample floor)
- **Observation:** loss-research-agent decisions are currently age-agnostic. 1-min-old positions at r≤-0.3R that have never gone green (mfe<=0) are structurally different from 60-min-old positions at the same r; the former failed 100% today.
- **Recommendation:** add position-age conditional to loss-research-agent skill file — when `age_minutes < 10` AND `r_curr <= -0.3R` AND `max_favorable_pnl_usdt <= 0`, default decision becomes EXIT_EARLY (medium confidence), override-to-HOLD only on identifiable current-bar fresh catalyst. Ship in MEASUREMENT-MODE first; depends on INSIGHT-20260511-007 (loss-research logger fields) for efficacy measurement.
- **Sequencing:** if INSIGHT-20260511-005 (rngpos hard-reject) ships first, this rule's target cohort may shrink (chase-entries blocked at fire time). Both should remain proposed; they target different stages.
- **Created:** 2026-05-11T18:15:00Z
- **Depends on:** ENH-17:20Z logger (so age_minutes and mfe-at-decision are captured for measurement)
- **See:** `memory/system-improvements.md` ENH-2026-05-11T18:15Z for full rationale.


## INSIGHT-20260512-001

- insight_id: INSIGHT-20260512-001
- category: exit / agent-decision-authority
- observation: The loss-research-agent's HOLD decisions had a 1W/7L track record today (12.5% win rate, net −0.975 USDT across 8 closed HOLDs), while EXIT_EARLY decisions cut losses an average of ~$0.20 below the resting SL per case (per journal notes "saved ~0.30 USDT vs SL hit" on HUSDT, ZECUSDT, etc.). Three HOLDs lost the full SL distance within 6-24 minutes of the decision (BILLUSDT 6min, UBUSDT 13min, ALCHUSDT 24min), and the pre-set "r ≤ −0.85R pre-SL exit" invalidation rules these HOLDs specified never fired because the 10-min loss-research cron interval was longer than the time-to-SL. 5 of 8 HOLDs were "medium" or "low" confidence — all 5 of those lost money. The lone winning HOLD (NAORISUSDT +0.39) was "medium" confidence but structurally well-reasoned. This is the first cycle to statistically audit the loss-research-agent's own decision accuracy.
- evidence:
    sample_size: 18 logged loss-research decisions today (11 HOLD + 7 EXIT_EARLY); 14 closed, 1 still-open (BUSDT)
    win_rate: HOLD = 1W/7L = 12.5%; EXIT_EARLY = 0W/7L by definition (deliberate cuts), but counterfactual SL-saving = ~$0.20/case avg
    avg_pnl: HOLD = −0.122 USDT/case; EXIT_EARLY = −0.146 USDT/case but saved $0.20 vs SL = net positive vs counterfactual
    regime: btc_flat_alt_rotation with intraday squeeze (LONG WR 53% / SHORT WR 23% — see ENH-2026-05-12T00:55Z)
    cases_full_sl_after_hold: 3/8 = 37.5% (BILLUSDT 6min, UBUSDT 13min, ALCHUSDT 24min)
- recommended_change: Two-part —
  PART A (auto-executable code-fix, low-risk, no behaviour change): extend the already-queued loss-research-logger (INSIGHT-20260511-007) to ALSO record the OUTCOME of each decision (close_timestamp, close_reason, realized_pnl, r_at_close, was_correct: bool) by joining against the close-event journal writer (INSIGHT-20260511-004). This makes the 12.5% HOLD WR measurable from data, not from manual cross-reference.
  PART B (rule-tweak, REQUIRES USER APPROVAL, tightens not loosens): when loss-research-agent emits decision=HOLD with confidence in {"low", "medium"}, orchestrator overrides HOLD → EXIT_EARLY. Only "medium-high" or "high" confidence HOLDs are honoured. Activation gated on 30+ logged decisions across ≥ 5 trading days per learning-policy small-sample floor.
  PART C (auto-executable code-fix, low-risk): add price-move-event-triggered re-evaluation — when r_curr drops ≥ 0.15R since last loss-research tick, fire loss-research-agent immediately instead of waiting for the 10-min cron. This closes the gap that let BILLUSDT/UBUSDT/ALCHUSDT hit full SL between HOLD and next tick.
- requires_user_approval: true for PART B; false for PARTS A and C (instrumentation + cadence fix, both fold mechanically into already-queued ENH-17:20Z logger plumbing)
- safety_impact: none — all three parts only tighten exit behaviour, never loosen. PART A is pure observability. PART B raises the bar on HOLDs (more EXIT_EARLY = lower live exposure on losing positions). PART C makes the existing pre-set invalidation triggers actually fire on time.
- expected_impact: quantified — if today's 5 medium-and-below HOLDs had been forced to EXIT_EARLY, estimated savings ≈ 5 × $0.20 avg = +$1.00 USDT/day at current trade frequency. Over a 30-day window with similar regime, ≈ +$30 USDT in saved drawdown.
- statistical_caveat: 1-day sample (n=15 closed decisions) is below the 5-day / 30-decision threshold from agency/learning-policy.md. Ship PARTS A + C immediately for measurement; defer PART B activation until 30+ samples confirm the pattern.
- falsifier: if across 30+ logged decisions, medium-confidence HOLDs achieve ≥ 40% win rate AND positive net P&L, PART B is wrong and must not activate.
- depends_on: INSIGHT-20260511-007 (loss-research logger), INSIGHT-20260511-004 (close-event writer) — both queued. Ship sequence: writer → logger → outcome reconcile → measurement window → rule-tweak proposal.
- created_at: 2026-05-12T01:25:00Z
- status: pending_user_approval
- see: `memory/system-improvements.md` ENHANCEMENT-2026-05-12T01:25Z for full rationale.

## INSIGHT-20260512-011 — MISSING TOOLING: scripts/run_close_position.py never wired; 5 high-confidence EXIT_EARLY verdicts BLOCKED today
- category: execution
- observation: scripts/run_close_position.py (referenced by scripts/telegram_bot.py:278) does not exist. Today's loss-research-agent produced 5 EXIT_EARLY verdicts on JELLYJELLYUSDT + SUIUSDT, ALL logged execution_status=BLOCKED_PENDING_USER_AUTH because no symbol-scoped reduce-only close path is wired. emergency_close_all closes ALL positions which is unacceptable scope. Estimated unrealised savings ~0.30 USDT today alone; this is the precondition for ENH-01:25Z HOLD-tightening and ENH-18:15Z age-conditional EXIT_EARLY to actually do anything.
- evidence: sample_size=5 BLOCKED verdicts of 23 total today (21.7% block rate); 4 distinct decisions on 2 positions; agent's own EV math: JELLY ~0.16 saved-vs-SL, SUI ~0.14 saved-vs-SL; regime btc_flat_alt_rotation full_auto_live
- recommended_change: PHASE 1 (auto-shippable): create scripts/run_close_position.py — single-symbol reduce-only MARKET close + cancel algo SL/TP + journal close-event + safety-event row; mandatory --symbol|--position-id + --reason + --i-understand flags. Update telegram_bot.py:278 to invoke it. PHASE 2 (user-approval required): orchestrator auto-invocation on BLOCKED_PENDING_USER_AUTH verdicts from loss-research-agent — shifts agency from "log and wait" to "auto-exit when high-conf invalidation fires".
- requires_user_approval: phase 1 NO (file dormant until invoked with --i-understand; mandatory flags + refuse-if-ambiguous prevent misfire). Phase 2 YES (changes live exit behaviour).
- safety_impact: none for phase 1 (file dormant; manual-only invocation; the existing primitives in live_execution.py already exist; this is purely a CLI wrapper composing them). Risk surface = operator-error path only.
- expected_impact: per-verdict user-action time 2-3min → 5sec (one CLI command vs JSON reconstruction). Phase 2 IF approved: ~0.30 USDT/case avg saved × ~5 BLOCKED verdicts/day = ~1.5 USDT/day = ~30-45 USDT/month at locked wallet scale.
- depends_on: NONE — independent of the keystones (ENH-16:00Z, ENH-17:20Z). Actually UNBLOCKS those because they need a place to call when their efficacy-measurement plumbing detects high-confidence EXIT decisions.
- falsifier: code search reveals scripts/run_close_position.py actually exists or another symbol-scoped close path the agent should be using. Verified today: ls returns "No such file or directory"; grep returns ONLY telegram_bot.py:278 hint.
- created_at: 2026-05-12T02:25:00Z
- status: RECOMMENDED_AUTO_SHIP_PHASE_1 — phase 1 auto-shippable; phase 2 pending_user_approval
- see: memory/system-improvements.md ENH-2026-05-12T02:25Z for full rationale.

## INSIGHT-20260511-018

- insight_id: INSIGHT-20260511-018
- category: exit
- observation: CLAUDE.md locked-policy R-multiple SL-trail schedule (>=0.9R BE; >=1.5R +0.5R; >=2.0R +1.0R; >=2.5R +1.5R) is NOT implemented in any live cron path. profit_protection.advise() has a single-tier BE-stub at 1.0R but is never imported/called by watcher or any cron script (only consumer is telegram_notifier.send_profit_protection_alert which is a notification helper, not an actuator). 2 of 5 currently-open agency-managed positions (FHEUSDT 1.09R, BUSDT 1.18R) crossed the 0.9R trigger this session; neither was trailed to BE. BUSDT gave back 0.77R (0.36 USDT) directly attributable to this gap.
- evidence:
  - sample_size: 2 (policy violations now)
  - open_positions_evaluated: 5
  - violation_rate_pct: 40.0
  - regime: btc_flat_alt_rotation full_auto_live
  - code_search: grep -rn "r_curr" scripts/ returns ZERO matches; grep -rn "0.9R" scripts/ returns ZERO matches; profit_protection.advise has zero non-telegram callers
- recommended_change: Create scripts/r_multiple_trail.py (pure function compute_r_trail_decision(pos, mark_price)). Add Position.initial_stop_loss field (set at open, immutable). Wire into watcher.py cron tick after compute_decision; route through existing _try_live_trailing cancel-and-replace plumbing (already safe per ERROR-20260511-5 fix). Pause-gate: refuse to act if safety_state.is_paused(). Tightening-only invariant already enforced by _try_live_trailing.
- requires_user_approval: true
- safety_impact: low — pure-positive expected value (BE is better than any negative outcome); "tighten only never widen" enforced by existing watcher plumbing; pause-gated; does NOT widen any SL, does NOT relax any risk gate, does NOT increase trade-firing rate
- type: code-fix / new-feature
- expected_impact: 0.3-0.5 USDT/session avoidable giveback at current 5-6 concurrent-position scale on 30 USDT wallet = 1-2% wallet/session protection floor
- complementary_to: ENH-2026-05-11T~15Z (MFE-pullback USDT-threshold rules also missing — different rule family, both unwired); ENH-2026-05-12T02:25Z (missing run_close_position.py CLI — same class of policy-mandated-mechanic-gap, different layer)
- depends_on: NONE — orthogonal to all queued keystones, can ship independently
- falsifier: code search reveals r-multiple trail schedule IS wired somewhere (e.g. a new scripts/scalp_monitor.py). Verified this cycle: not present.
- created_at: 2026-05-11T21:23:44Z
- status: PENDING_USER_APPROVAL — module creation is risk-free auto-shippable; watcher wiring activates previously-dormant policy behavior, requires explicit user signoff per learning-policy "never override Risk Manager defaults"
- see: memory/system-improvements.md ENHANCEMENT-2026-05-11T21:23Z for full rationale.

## INSIGHT-20260512-012 — Reconciler detect-only; no auto-finalize write-back; phantom pause class
- category: reconciliation
- observation: scripts/binance_position_sync.py + scripts/run_reconcile.py DETECT `missing_on_exchange` mismatches and PAUSE trading (via record_health(...pause_on_mismatch=True)), but never AUTO-WRITE the local close using exchange truth. SignedClient has no `get_user_trades` wrapper at all (grep `userTrades|user_trades` in scripts/ returns 0). Tonight: JELLY SL fired ~21:09Z; risk-state still shows pause active 6+ hours later with reason="position-manager mismatch (1 entries)". Pattern recurs (BUSDT 13:52:07Z, same flow note "live_mode_skipped_local_exit:stop_hit (price hit stop 0.4514); exchange-side close required").
- evidence: sample_size 2; phantom_pause_duration_h 6.7; loss-research decisions blocked during pause 9; endpoints missing [GET /fapi/v1/userTrades]; regime btc_flat_alt_rotation FULL_AUTO_LIVE
- recommended_change: Create scripts/run_reconcile_finalize.py (or `--finalize-closed` flag on run_reconcile). Add SignedClient.get_user_trades(symbol, startTime, endTime, limit). For each missing_on_exchange mismatch: fetch userTrades since opened_at-5min, walk fills tracking net qty, identify closing reduceOnly fill, write status=closed + exit_price + realized_pnl (from Binance reported field) + new exit_reason="exchange_closed_auto_reconciled" to positions_store. Only after ALL mismatches resolved AND pause_reason matches "position-manager mismatch" prefix, call safety_state.resume(). Refuse-on-ambiguity (zero fills, partial close, race conditions). Dry-run flag mandatory for first deployment.
- requires_user_approval: true
- safety_impact: low — write-back uses exchange truth (already-happened events), not predictions; auto-resume scope narrowly gated to mismatch-pause prefix only (daily-loss, consecutive-loss, kill-switch pauses untouched because they have different pause_reason prefixes set by safety_state.pause); refuse-on-ambiguity prevents speculative writes; dry-run flag; full unit test coverage required
- type: code-fix / new-feature
- expected_impact: eliminates ~1 phantom pause per session, each blocking 30min–6h of FULL_AUTO_LIVE firing. Tonight alone: 6.5h+ phantom pause + 9 blocked exit decisions + ~0.50 USDT estimated giveback that protective actions could have avoided.
- complementary_to: ENH-2026-05-12T02:25Z (run_close_position CLI — both share need for SignedClient.get_user_trades; sensible to land together as a single "exchange ↔ local state write-back loop" closure)
- depends_on: NONE — orthogonal to R-trail (ENH-21:23Z), MFE-pullback (ENH-14:55Z), audit writers
- falsifier: code search reveals an auto-finalizer exists that writes status=closed using userTrades for missing_on_exchange mismatches. Verified this cycle: grep returns ZERO matches for userTrades; position_manager.py:116 emits the mismatch only; binance_position_sync.py:151 loop only persists `missing_locally` (the opposite direction).
- created_at: 2026-05-12T02:55:00Z
- status: PENDING_USER_APPROVAL — module creation + SignedClient.get_user_trades + dry-run mode are risk-free auto-shippable; wet-mode write-back + auto-resume scope requires explicit user signoff per learning-policy "never override Risk Manager defaults" (auto-resume is a defaults-modification even though scope is narrow)
- see: memory/system-improvements.md ENHANCEMENT-2026-05-12T02:55Z for full rationale.

## INSIGHT-20260512T2321Z-SYNCED-FILE-STALENESS-NO-GATE

- insight_id: INSIGHT-20260512T2321Z-SYNCED-FILE-STALENESS-NO-GATE
- category: system_integrity / data_freshness
- observation: `data/synced-binance-positions.json` is the agency's authoritative cross-check for live exchange state (used in watcher cross-verification, reconciler logic, position-count gates, and human review). The file embeds a `synced_at` field — but **no downstream script reads `synced_at`** to validate freshness before acting. Confirmed via `grep -rn synced_at scripts/`: only producer `binance_position_sync.py` writes it; **zero consumers** check the age. Current snapshot illustrates the risk: `synced_at = 2026-05-11T21:21:28Z` while host clock is `2026-05-11T23:21:15Z` — a **~2 hour staleness gap**, yet local `open-positions.json` was updated `23:21:13Z` (2 sec ago). Any guard that compares "local vs synced" to detect drift currently treats a 2-hour-stale snapshot as authoritative, which means an exchange-side liquidation, manual close, or out-of-band fill that happened in the last 2 hours would be **invisible to every cross-check**. This is the silent failure mode behind the user's prior complaint about "8 false closure claims tonight" — the watcher had no way to know its reference snapshot was outdated.
- evidence:
    sample_size: 1 live snapshot inspected at 23:21:15Z showing 7,193 second staleness in synced file
    consumers_checked: 0 of N consumers of synced-binance-positions.json validate synced_at age (grep across scripts/ for `synced_at` outside the producer returns no hits)
    related_bugs: ERROR-20260511-4 (watcher local-trailing closures), 8 false closure claims tonight, INSIGHT-20260512-012 (reconciler detect-only) — all share a common root: assuming the synced file is fresh
    cross_file_divergence_now: local open-positions has 6 open (FHE/JELLYJELLY/BUS/SUI/LAYER/USELESS); synced has 5 (missing JELLYJELLYUSDT). With 2hr staleness, agency cannot tell whether JELLYJELLY is a real live position the sync missed, a phantom local record, or an interim event
- recommended_change: Add a single shared freshness helper, e.g. `scripts/sync_freshness.py::assert_synced_fresh(max_age_seconds=300)`, which: (1) reads `synced-binance-positions.json`, (2) parses `synced_at`, (3) returns `(is_fresh: bool, age_seconds: int, synced_at: str)`. Then call it as a **gate** (warning-only initially, log-only — no behavior change) in: watcher cross-verification path, reconciler, position-count gate, and any "compare local vs synced" code path. After 24-48hr of warnings-only telemetry, escalate to hard-block (refuse to act on cross-source comparison if synced age > 5min when the live-signed gate is open). Pair with an auto-trigger: if age > 60s during a live session, fire `binance_position_sync.py` once before proceeding. **No risk-parameter changes. No new orders. No .env changes.** Pure observability + a defensive read-side gate.
- requires_user_approval: false for the freshness helper + warning-only logging (non-risk code-fix, observability addition). true for the hard-block escalation after telemetry review.
- safety_impact: low for warning-only phase; medium-positive for hard-block phase (closes a silent-failure class without raising risk).
- new_angle: This is distinct from the 22 queued findings:
    * NOT the same as the "watcher cross-verification meta-fix" (that one fixes false claims after they're produced; this one prevents the upstream input from being silently stale)
    * NOT the same as "reconciler write-back" (that one finalizes detected diffs; this validates the diff input is fresh enough to trust)
    * NOT the same as "multi-stream verifier" (that one queries premiumIndex + positionRisk + local; this gates the existing synced cache so consumers don't unknowingly use a 2-hour-old snapshot)
- created_at: 2026-05-11T23:21:30Z
- status: pending

## INSIGHT-20260512T0345Z-CROSS-MARGIN-LIQUIDATION-CASCADE
- category: safety
- observation: USELESSUSDT (user-opened, margin_type='cross', 21x, ~9x wallet notional, ~88% wallet blast-radius) has a documented emergency-exit trip-price ($0.0670) written ONLY as English text in data/open-positions.json notes[] line 2338. No Python script reads the note. The watcher has zero cross-margin awareness (grep over scripts/*.py returns zero evaluators of margin_type, only the sync-side READER in binance_position_sync.py). A single cross-margin liquidation consumes the entire wallet, not an isolated 3.5-USDT slot. Liquidation buffer hit 1.5% overnight per notes — the trip-price has already been approached.
- evidence:
    - sample_size: 1 (cross-margin position currently open)
    - documented_near_miss_buffer_pct: 1.5
    - wallet_blast_radius_pct: ">=88"
    - code_paths_handling_cross_margin: 0
    - code_paths_reading_trip_price_notes: 0
    - regime: user-managed cross-margin overlap on small wallet
- recommended_change:
    1. SHIP-1 (auto-executable, low-risk): create scripts/cross_margin_safety_monitor.py — dry-run-default, read-only, emits WARNING (<5% buffer) and CRITICAL (<2% buffer or trip-price match) telegram alerts. Add optional `cross_margin_emergency_trip_price: Decimal | None` field to Position dataclass.
    2. SHIP-2 (REQUIRES USER APPROVAL): promote --execute mode that overrides USER_MANAGED skip and fires reduce-only MARKET close when trip-price matches. This is the only path in the codebase that overrides USER_MANAGED; override is narrowly bounded to (margin_type==cross) AND (explicit trip-price set) AND (LIVE mode) AND (mark-price non-stale).
    3. Optional cron entry */2 * * * * dry-run mode after ship-1.
- requires_user_approval: true (for ship-2; ship-1 is safe to auto-execute)
- safety_impact: PROTECTIVE — REDUCES wallet-wipe tail risk by codifying a single-point-of-failure off the honour system. Dry-run ship is risk-free (alerts only). Wet-mode override requires user approval because miscalibration of trip-price could close a user-held position prematurely; mitigated by refuse-on-ambiguity guards (stale-mark, isolated-margin-skip, non-LIVE-skip, missing-trip-price-skip).
- type: new-feature
- expected_impact: eliminates the silent-fail mode where the documented trip-price is text-only. Frequency: every user-opened cross-margin position introduces this risk class. Tonight there is 1 (USELESS, near-miss already on record). Each occurrence is an unbounded-duration wallet-wipe risk window (hours to days, depending on user trade horizon).
- complementary_to: ENH-2026-05-12T02:25Z (run_close_position CLI — wet-mode ship-2 would call into this for the actual close); ENH-2026-05-11T17:30Z (USER_MANAGED skip design — this is the explicit code-level CARVE-OUT for the one safety class where the skip would cost the entire wallet).
- depends_on: NONE for ship-1. ship-2 depends on run_close_position CLI (ENH-02:25Z) being available as the close-execution primitive.
- falsifier: code search reveals a module that (a) reads margin_type=='cross' AND (b) compares mark-price to a stored trip-price AND (c) emits alert/close-action. Verified this cycle: grep -rn "margin_type\|marginType\|cross_margin" scripts/*.py returns only the sync-side reader and an unrelated comment in watcher.py — zero evaluators, zero decision-points, zero alerts.
- created_at: 2026-05-12T03:45:00Z
- status: PENDING_USER_APPROVAL — ship-1 (dry-run + alerts + dataclass field) recommended for auto-execute via error-fix-agent; ship-2 (wet-mode override of USER_MANAGED) explicitly user-gated.
- see: memory/system-improvements.md ENH-2026-05-12T03:45Z for full rationale.

---

## INSIGHT-2026-05-12T04:05Z — pause-state has no duration SLA and no escalation ladder; silent paralysis is the failure mode
- observation: tonight a pause set at 2026-05-11T20:13:01Z persisted ≥ 7h 50m with exactly ONE Telegram message (at trigger time). 0 trades fired all night. User manually traded USELESS during the silence and whipsawed −$10 → +$5. Agency's protected book held +$0.50–0.80.
- root_cause: `safety_state.SafetyState.paused_at` is WRITE-ONLY — no call site computes `now - paused_at`, no consumer alerts on age, no automated re-check of the trigger condition after N minutes. Operator has no clock ticking anywhere visible.
- proposal: (1) add derived `pause_age_seconds` to state.to_dict(); (2) add escalation ladder (15m / 1h / 4h / 12h / +6h thereafter) via dedup-aware reminder cron piggy-backing on the watcher tick; (3) at the 4h threshold, auto-spawn a discovery-agent dry-run that re-checks whether the original trigger condition still applies, and raise alert urgency if it has cleared — but DO NOT auto-resume (manual resume preserved as the safety contract).
- requires_user_approval: true (notification policy + new state field)
- safety_impact: PROTECTIVE / observability-only. Does NOT auto-resume, does NOT change risk limits, does NOT fire trades. Worst-case failure mode is "Telegram noisy" — bounded by dedup + per-threshold once-only sends.
- type: new-feature (observability + escalation)
- expected_impact: replaces tonight's 1-message-in-8h failure with at minimum 3 escalations + a 4h auto-recheck. Direct mitigation of operator-whipsaw-cost during silent windows. Each silent pause-hour historically correlates with operator manual trading (high variance, recently a $15 swing).
- complementary_to: ENH-2026-05-12T02:55Z (reconciler write-back would prevent the SPECIFIC pause-cause tonight) and ENH-2026-05-11T16:00Z (canonical-paths — agents-don't-know-they-are-paused class). This finding is orthogonal: even with both fixed, ANY future pause from ANY cause has no clock today.
- depends_on: NONE — purely additive to safety_state + reuses existing Telegram notifier and existing watcher cron cadence.
- falsifier: grep finds any module reading `paused_at` for age computation or any cron emitting periodic pause reminders. Verified this cycle: only `safety_state.py` writes the field; `data/risk-state.json` shows the stale 8h-old value with zero downstream consumers.
- created_at: 2026-05-12T04:05:00Z
- status: RECOMMENDED_USER_APPROVAL — small PR (derived field + escalation script + dedup state field). Suggest 7-day warn-only mode (log to file before Telegram) to tune dedup thresholds before production.
- see: memory/system-improvements.md ENH-2026-05-12T04:05Z for full rationale.
