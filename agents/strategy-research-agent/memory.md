# Strategy Research Agent — Memory

This file is a topic-organized, deduped current-state summary of what the agent has learned. The chronological log lives in `memory/strategy-research-log.md`.

## Active research-question rotation queue

(Cycle through these. After a topic is researched, move it to the bottom.)

**Note 2026-05-12T19:35Z:** This fire researched an OFF-QUEUE topic ("cry-wolf / alarm fatigue") motivated by tonight's 7 blocked EXIT_EARLY verdicts. Rotation queue position unchanged — next fire should still pick item #1 (News-catalyst trading) unless another session-specific event takes priority. Cry-wolf entry added to topic library below.

**Note 2026-05-12T20:15Z:** Second consecutive off-queue fire — researched "carry-over pause UX / graded kill switch" motivated by tonight's safety-pause-blocked BE-trails on FHE (r=+1.0) and BUSDT (r=+1.14). Rotation queue position STILL unchanged — next fire MUST pick item #1 (News-catalyst trading) unless a third session-critical event takes priority. Pause-scope entry added to topic library below. Two off-queue fires in a row is the limit; if a third session-event arises, escalate to user before going off-queue again.

**Note 2026-05-12T20:55Z:** Back on rotation — fired item #1 (News-catalyst trading). Two strongest empirical sources: Keyrock 16,000-unlock study (90% negative, decline 30d before, peak impact T-2d) + BitPinas/CryptoNinjas 389-token Binance-listing study (98% post-listing dump, 87% initial pump, 46% ATH-at-listing). Topic library "News catalysts" section now populated. Item #1 rotates to bottom; next fire takes item #2 (Volatility-adjusted position sizing / ATR-based sizing).

**Note 2026-05-12T21:30Z:** Fired item #1 in new ordering (Volatility-adjusted position sizing). Three corroborating sources (LuxAlgo, FXNX, Setup4Alpha). Core finding: for fixed-margin systems, ATR-sizing re-expresses as `effective_leverage = min(confidence_tier, ATR_cap)` — margin stays 3.5, 1R stays $0.10, leverage flexes inversely with ATR(14, 5m)-as-%-of-price. LuxAlgo cites 25% drawdown reduction (multi-asset, no specific window). FXNX explicit scalp multiplier: 1.5×-2.0× ATR. Mapping proposed (5-tier ATR-cap overlay). Topic library "Volatility sizing" section now populated. Item #1 rotates to bottom; next fire takes item #2 (Market-regime classification).

**Note 2026-05-12T22:00Z:** Fired item #1 in current ordering (Market-regime classification). Five sources (LuxAlgo, QuantMonitor, Thrive, Preprints HMM Bitcoin study, TradingView HMM-LuxAlgo script). Core finding: 2×2 trend-sign × volatility-state matrix (computed from SMA-50 slope sign + ATR-percentile rank over 252 5-min candles) collapses to 5 regimes (UP_LOWVOL / UP_HIGHVOL / DOWN_LOWVOL / DOWN_HIGHVOL / RANGE). LuxAlgo quotes +10-30% risk-adjusted return improvement / similar DD cut from regime-aware strategy switching (multi-asset daily/4h — transfer to 5-15 min decimal-perp scalps unverified). Mapping proposed: diagnostic-only `regime_at_entry` field on trade-journal records, NO filter, NO confidence nudge, NO risk-param change. After ≥ 30 trades with tag attached, scatterplot WR × regime × strategy-type → propose regime-conditional confidence nudges (not hard filters). HMM-based classifier NOT recommended (too much code surface for wallet size). Topic library "Regime classification" section now populated. Item #1 rotates to bottom; next eligible un-cooldown item is item #2 (Profit-target optimization, flagged "revisit after material wallet/edge change") — in practice, next fire should re-scan the list for the first uncooled topic.

**Note 2026-05-12T22:35Z:** All 10 enumerated rotation items are currently cooldown-gated (each requires N≥30 trades with a new diagnostic field, post-implementation deltas, or material wallet/edge change). Rather than waiting, this fire opens an 11th library slot: **Liquidity-cluster magnets + CVD-divergence confirmation**. Five sources reviewed (Zipmex, Coinglass Pro, Glassnode Insights, Bookmap, Phemex Academy + LuxAlgo CVD page). Core finding: sweep-and-reverse off liquidation clusters paired with CVD-divergence at known reference levels is the cleanest off-the-shelf scalp-horizon entry-confirmation stack — directly endorsed for 5-15 min in CVD literature, fits our hold horizon precisely. Critically, **CVD-approx is computable for zero extra API cost** from Binance `/fapi/v1/klines` `takerBuyVolume` field we already fetch. Mapping proposed: diagnostic-only `cvd_5m_approx` + `liquidation_context_at_entry` fields, NO filter, NO confidence nudge, NO risk-param change. Liquidation-cluster data deferred (paid Coinglass Pro, decimal-coin data quality uncertain) — start with CVD-only. After ≥ 30 trades with `cvd_5m_approx` tagged, scatterplot WR × {divergence-yes/no} × {direction-with/against}. New topic library entry "Liquidation clusters + CVD divergence" added below. Rotation queue position UNCHANGED — when items #1-#10 cooldowns expire, normal rotation resumes; this slot becomes #11 with first-research cooldown "≥ 30 trades with `cvd_5m_approx` attached."

1. Profit-target optimization for small-wallet leveraged futures [LAST RESEARCHED 2026-05-11; revisit in 30+ days or after material wallet/edge change]
2. Scalp-exit research: optimal MFE-pullback thresholds beyond locked rule [LAST RESEARCHED 2026-05-11T15:53Z; revisit after ≥ 30 closed trades enable empirical scatterplot]
3. Decimal-priced token edge [LAST RESEARCHED 2026-05-11T16:25Z; revisit after rngpos hard-reject decision lands + ≥ 20 post-implementation trades for before/after delta]
4. Funding-rate squeeze setups (negative funding mean-reversion) [LAST RESEARCHED 2026-05-11T16:55Z; revisit after diagnostic funding-rate logging produces ≥ 30 trades of empirical sign-vs-outcome data]
5. Open-interest delta interpretation [LAST RESEARCHED 2026-05-11T18:23Z; revisit after diagnostic OI-delta logging produces ≥ 30 trades of empirical sign-vs-outcome data, OR after rngpos & funding filters land first]
6. Time-of-day session edge (Asia open / NY open / weekend distortion) [LAST RESEARCHED 2026-05-12T19:17Z; revisit after `analyze_entry_hour_pnl.py` diagnostic exists + ≥ 50 trades bucketed by hour-UTC for our specific alt-scalp universe]
7. R:W expectancy math — fee-adjusted BE-WR sensitivity under tightened max-loss [LAST RESEARCHED 2026-05-12T00:00Z; revisit after diagnostic `fee_burden_pct_of_1R` is logged on ≥ 30 trades, or if user changes max-loss / fee tier again]
8. News-catalyst trading: listing pumps, exchange announcements, unlock fades [LAST RESEARCHED 2026-05-12T20:55Z; revisit after `data/calendar-layer.json` diagnostic exists + ≥ 30 trades cross-referenced against unlock/listing dates for empirical bias-vs-outcome data]
9. Volatility-adjusted position sizing (ATR-based sizing within fixed margin) [LAST RESEARCHED 2026-05-12T21:30Z; revisit after `atr_pct_at_entry` is logged on ≥ 30 trades for empirical ATR-bucket × leverage-tier × outcome scatterplot]
10. Market-regime classification — practical 2×2 trend × vol taxonomy [LAST RESEARCHED 2026-05-12T22:00Z; revisit after `regime_at_entry` field is logged on ≥ 30 trades for empirical regime-bucket × WR × strategy-type scatterplot]
11. Liquidity-cluster magnets + CVD-divergence confirmation [LAST RESEARCHED 2026-05-12T22:35Z; revisit after `cvd_5m_approx` field is logged on ≥ 30 trades for empirical divergence × direction × outcome scatterplot]

## Topic library — current best practices

(Filled in as the agent researches. Each topic has: technique → mechanic → source → fit-with-our-policy → risk-if-wrong.)

### Profit-target optimization

**Established (Van Tharp R-multiple framework, citation chain via pnlledger.com & Wikipedia Kelly):**

1. **Expectancy-in-R is the master metric, not daily-USDT target.** Formula: `E = p × AvgWinR + (1-p) × AvgLossR`. Source: https://www.pnlledger.com/expectancy-r-multiples-the-plain-english-guide/

2. **Our current expectancy (2026-05-11):** +0.39R per trade at 1R = 0.50 USDT max-loss → +0.195 USDT/trade. At 13 trades/day = +2.53 USDT/day. This already represents 8% daily ROI on 30 USDT, which is top-decile professional performance.

3. **$10/day on a 30 USDT wallet = 33%/day** — this rate is mathematically NOT sustainable at our verified edge under locked policy. To reach it we would need:
   - Avg-win 5x larger (UNREALISTIC on 5-15 min scalps), OR
   - 51 trades/day (VIOLATES discipline + per-cycle cap), OR
   - Higher leverage / larger position size (FORBIDDEN — exceeds Kelly safety)

4. **Kelly cross-check (Wikipedia https://en.wikipedia.org/wiki/Kelly_criterion):** With WR=0.5 and reward:risk b=3.2, full Kelly = 34.4% of wallet per bet. Half-Kelly = 17.2%. Recommended fractional Kelly is ¼ to ½ for real trading with edge uncertainty. **Our current deployment of 93% of wallet across 8 correlated positions is closer to FULL Kelly than half-Kelly.** Wikipedia explicit warning: "betting an amount larger than the Kelly amount increases the risk of ruin."

5. **Caveat: Kelly assumes independent bets.** Eight concurrent alt-futures positions are correlated (especially during BTC-led moves). Effective Kelly fraction is LOWER than the binary formula suggests — possibly by 2-3x. Established quant practice (no single cited URL — common knowledge in pairs-trading literature; flag as needs-validation).

6. **Realistic ceiling under locked policy on 30 USDT:** +2.5 to +5 USDT/day = 8-17%/day net. The $10/day target becomes natural once wallet compounds to ~60 USDT (≈6 days at +5/day net); same percentage edge then produces $10/day in absolute terms.

**Speculative (label as such — requires backtest before any action):**

- Whether reducing concurrent slots from 8 → 5 raises per-trade expectancy due to less attention-dilution and better selection bias. No published evidence for our specific setup.
- Whether expectancy-in-R logged daily in `data/risk-state.json` would help the user spot regime shifts faster than current PnL-only view.

**Action recommendations (NO risk-param changes, user-decision only):**
- Reframe daily target from absolute USDT to **% of wallet** (10-15%/day = +3 to +4.5 USDT on 30 USDT wallet; +6 to +9 USDT once wallet hits 60).
- Track expectancy-in-R daily — non-risk, deterministic; could be queued to error-fix-agent only with user approval.

### Scalp-exit optimization

**Established (Sweeney 1996 + Dobrovolsky 2002 + Kaufman *Trading Systems and Methods* 6e, 2020):**

1. **MFE-pullback thresholds should be DATA-DERIVED from one's own trade scatterplot, not borrowed.** Methodology: plot every trade's final-PnL vs MFE peak; find the giveback level where empirical probability of continued favorable excursion crosses your marginal-utility-of-waiting. Source: John Sweeney, *Maximum Adverse Excursion* (Wiley, 1996) — summary https://dokumen.pub/maximum-adverse-excursion.html, https://journalplus.co/learn/glossary/mae/; Dobrovolsky, *Setting Stops And Taking Profits With Maximum Excursion*, S&C Aug 2002 — http://traders.com/documentation/feedbk_docs/2002/08/Abstracts_new/Dobrovolsky/dobrovolsly.html

2. **Scalp capture-efficiency norm: 50-65% of MFE.** Scalps legitimately capture less than swing trades because they target small moves with tight timing. The 65-80% range is the practical optimum for discretionary strategies. Source: TradeWink summary — https://www.tradewink.com/learn/mfe-mae-trade-quality (search-snippet only; page is 403-protected). **Implication: a giveback rule that lets us capture only 20-30% of MFE is below the scalp norm and is leaving money on the table.**

3. **Industry generic "exit on 50% giveback from MFE" is a swing-trade heuristic, NOT a scalp rule.** For scalps the documented practice is tighter (30-50% giveback tolerance).

4. **Chandelier Exit (Le Beau, in Elder)** is the dominant alternative — uses ATR-multiple from highest-high. Standard 3× ATR (22-period) for trends; 1.5-2× ATR for scalps. Self-scales with volatility (a property our fixed-USDT pullbacks lack). Sources: https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/chandelier-exit, https://www.quantifiedstrategies.com/chandelier-exit-strategy/

5. **Diagnostic metric: Exit Efficiency = realized_pnl / max_favorable_pnl.** Healthy scalp system targets 0.50-0.65. We currently don't compute this aggregate. Sources: TradingMetrics docs — https://docs.tradingmetrics.com/en/technical-analysis/trading-metrics/trade-specific-metrics/max-favorable-excursion

**Speculative (label as such — no published evidence specific to our setup):**

- **Time-based exit ("close if MFE not exceeded for N minutes")** is mentioned in discretionary scalping guides but has no peer-reviewed or named-trader backtest. Treat as needs-own-backtest before adoption.
- **No Monte-Carlo paper found** comparing fixed-R-trail vs MFE-pullback vs hard-cap-at-N-USDT for small-account crypto futures. The three-way comparison must be our own backtest.
- **MFE-magnitude-tiered giveback (50% at small MFE, 25% at large MFE) — our current pattern — is uncommon in published material.** Most cited systems use either a single % giveback or ATR-multiple from peak. Doesn't mean we're wrong; means we have no off-the-shelf validation.

**Mapping to our locked Rule B:**

Our tiers: MFE ≥ 1.0 → 0.25 USDT giveback (25%); MFE ≥ 0.50 → 0.15 (30%); MFE ≥ 0.30 → 80% giveback (uPnL ≤ MFE × 0.20). Today's empirical: rule fired 4-5 times, captured ~+1.07 USDT = 44% of day's net. Avg-win-after-rule-fire +0.34 vs system avg-win +0.567 → fires on smaller-than-typical wins. The 80%-giveback small-MFE tier is loose vs scalp norm (50-65% capture).

**Action recommendations (NO risk-param changes auto-applied):**

1. **Diagnostic script `scripts/analyze_mfe_exit_efficiency.py`** that reads `data/trade-events.jsonl` + trade-journal, computes per-trade exit-efficiency, outputs histogram by MFE-tier + suggested empirical giveback knee where hazard-rate-of-new-high < 30%. This is **diagnostic-only**, not a threshold change. Queue to error-fix-agent only with user OK.

2. **Speculative refinement (HYPOTHESIS, requires ≥ 30-trade scatterplot before user approval):** small-MFE tier (≥ 0.30) 80% giveback may be loose. If scatterplot shows trades hitting 0.30 MFE rarely push to ≥ 0.45 MFE (< 30% of time), tighten to 60-65% giveback. **Do not auto-apply.**

3. **Long-term consideration (label SPECULATIVE):** ATR-self-scaling pullback rule would track market volatility better than fixed USDT. Needs implementation cost-benefit study first.

**Risk if applied wrong:**
- Tightening giveback too much → cuts winning trades short before they reach TP, raises capture % per trade but lowers raw win size.
- Loosening giveback too much → exactly the give-back-to-loss outcome the rule exists to prevent (today's TRUTH +0.68 captured because the rule fired; without it, TRUTH could have given back to breakeven or worse).
- Therefore: do not change thresholds without ≥ 30-trade empirical scatterplot evidence.

### Decimal-priced token edge

**Established (cited):**

1. **Penny-stock anomaly carries over.** Alpha Architect / IBKR research summary: low-priced stock universe shows SD **29% vs 19%** for higher-priced peers (~53% higher SD) and Sharpe **−2.06 vs +0.61**. The lottery-ticket distribution that attracts traders also delivers asymmetric drawdown. Decimal USDT-M perps (BILL, UB, NAORIS, SAGA, SKYAI tier) share the micro-cap profile. Source (snippet only; both URLs 403-blocked on direct fetch): https://alphaarchitect.com/low-priced-stocks/, https://www.interactivebrokers.com/campus/ibkr-quant-news/explaining-the-performance-of-low-priced-stocks-the-penny-stock-anomaly/

2. **Tick-size as % of price is the hidden lever.** Each tick is 0.25–1.0% on a 0.0040 token vs < 0.001% on BTC — orders-of-magnitude noisier. Binance reduced tick sizes on USDⓈ-M perps (2024-09-20) explicitly to tighten spreads, confirming the structural issue. Sources: https://databento.com/microstructure/sub-penny-rule, https://www.binance.com/en/support/announcement/updates-on-tick-size-for-multiple-usd%E2%93%A2-m-perpetual-futures-contracts-2024-09-20-fa192e78242d4d96be9562ab7d76a10a

3. **Round-number clustering empirically confirmed in crypto.** Mbanga (2022, Finance Research Letters, ScienceDirect): clustering present for ETH/XRP/LTC, **stronger at high-frequency timeframes** (1m–15m, where our scalps live). Implication: stops cluster below round numbers; take-profits cluster below round numbers — so the top of an intraday range is mechanically a sell-pressure cluster. Sources: https://www.sciencedirect.com/science/article/pii/S1544612322001179, https://tradeciety.com/the-order-clustering-effect-around-round-numbers, https://coinpedia.org/traders/price-action-mastery-round-numbers-and-their-crypto-trading-impact/

4. **Wide relative spreads eat scalp edge.** Saxo + Britannica: execution risk on penny names is dominated by wide bid–offer spreads. For a 0.50 USDT loss budget at 5–15x on a decimal token, 2-tick entry slip can consume 10–20% of budget before the position forms. Sources: https://www.home.saxo/learn/guides/equities/penny-stocks-explained-what-they-are-and-why-you-should-care, https://www.britannica.com/money/penny-stock-trading

**Today's empirical match (2026-05-11):** Two losers (BILL −0.45, UB −0.30, combined −0.75) were rngpos ≥ 90% chase entries on decimal tokens. Combined = ~47% of day's gross erosion. The literature-supported diagnosis is precise: high-rngpos entry on a decimal token buys into both (a) elevated per-tick % noise AND (b) round-number sell-cluster — the worst combination.

**Speculative (label as such):**

- Whether Binance's 2024 tick-size cuts on low-priced perps have measurably tightened OR widened our realized slippage vs 6 months ago — no public study; needs our own pre/post analysis from `data/trade-events.jsonl`.
- Whether decimal-token range-top sell clusters are more pronounced than for major-priced perps in 5–30 min scalp windows specifically — no peer-reviewed crypto-futures source isolates this; Mbanga (2022) finding is generic.
- Penny-stock-anomaly SD/Sharpe numbers come from equities not perps. Direction same (low price → high noise); magnitude on Binance Futures may differ. Treat 53%-higher-SD as directional, not literal.

**Action recommendations (NO risk-param changes; user-decision queued):**

1. **Support enhancement-agent's existing rngpos hard-reject proposal.** Today's data + cited microstructure literature both support it. NO change to margin/leverage/max-loss/daily-cap/min-confidence.

2. **Refinement worth queueing for user OK: tier the rngpos threshold by price.** ≥ 0.85 hard-reject on decimal-priced (price < 1.0 USDT); ≥ 0.90 hard-reject on all symbols. Rationale: decimal tokens carry double-penalty (penny-anomaly volatility + round-number clustering at every 0.000X step); major-priced tokens carry only the clustering penalty.

3. **Expected lift (quantified, no risk change):** today's −0.75 chase-entry loss-cluster would have been avoided. Net would have been ~+2.35 instead of +1.6 (+47% lift). Daily expectancy lifts from +0.39R toward +0.54R — still below the "rare > 0.5R" threshold flagged on luxalgo.com, but a material non-risk-touching improvement.

**Risk if applied wrong:**

- Blanket rngpos hard-reject can miss legitimate breakout continuations on strong-trend days (Tradeciety: round-numbers act as resistance OR launchpads depending on context). Mitigation: pair rngpos filter with trend-confirmation overlay (EMA alignment + volume expansion) rather than blanket reject.
- Threshold too tight → reduces trade count → may push us below 13/day average → may not hit even +2.5/day floor on lower-edge days.

### Funding-rate squeezes

**Established (cited):**

1. **Canonical extreme threshold ±0.05%/8h funding interval = top/bottom 10th percentile** (consensus across CoinAPI, Yellow.com, BingX). March 2020 BTC bottom: −0.05% to −0.15% per interval for multiple cycles preceded recovery rally. Sources: https://yellow.com/learn/how-to-read-funding-rates-crypto-reversals, https://www.coinapi.io/blog/historical-data-for-perpetual-futures, https://bingx.com/en/learn/article/what-is-funding-rate-arbitrage-guide-for-futures-traders

2. **Funding-extreme alone is NOT a trade signal (Flipster).** Confirmed entries require a 4-signal stack: (a) RSI > 70 short / < 30 long, (b) price outside Bollinger band, (c) doji/engulfing/volume-spike candle, (d) funding extreme. Funding without the other three has high false-signal rate during trends. Source: https://flipster.io/en/blog/mean-reversion-in-crypto-how-to-trade-oversold-and-overbought-perps

3. **Altcoin caveat: thinner books → more extreme funding is normal-tape, not stretched (BingX).** Direct translation of BTC ±0.05% threshold to small-cap decimal-priced perps is unsafe. Slippage on entry can exceed a single funding payment in thin books. Source: https://bingx.com/en/learn/article/what-is-funding-rate-arbitrage-guide-for-futures-traders

4. **Funding can pin at floor/ceiling during strong trends (BitMEX Q3-2025).** Mean-reversion timing is unbounded — "a trader who shorts purely because rate is high can sustain significant losses before any reversal materializes" (Yellow.com). Symmetric on negative funding + long entry. Sources: https://www.bitmex.com/blog/2025q3-derivatives-report, https://yellow.com/learn/how-to-read-funding-rates-crypto-reversals

**Today's empirical match (2026-05-11):** Same-symbol re-entry pattern (BILL 3x, ALCH-reentry, UB SL after 1 min, BLUAI re-entry currently −0.14R) is structurally identical to "entering on the paying side of funding flow during a one-direction continuation." Strategy-agent today entered these at rngpos ≥ 85% with no funding-rate filter — exactly the high-tick-noise + paying-funding + chasing-trend stack the literature warns against.

**Speculative (label as such):**

- Whether funding-rate sign alone (regardless of magnitude) would have flagged today's BILL/UB/ALCH/BLUAI losses as bad re-entries — needs our own backtest from `data/trade-events.jsonl` × Binance historical funding.
- Whether a "funding-rate veto on third re-entry within 4h" specifically would have prevented BILL's 3-attempt cluster — speculative; same-symbol streak count is a non-funding proxy that may already capture most of this signal.
- No published peer-reviewed crypto-futures backtest specific to 5–15 min scalp horizon found.

**Action recommendations (NO risk-param changes, user-decision queued):**

1. **Diagnostic-only:** add Binance funding-rate fetch (`/fapi/v1/premiumIndex`) to strategy-agent's pre-trade context. Log funding sign + magnitude on every proposal. NO filter applied yet — pure observation for ≥ 30 trades before any rule proposed. Queue to error-fix-agent only with user OK.

2. **Speculative hypothesis (requires ≥ 30-trade evidence first):** on same-symbol re-entry within 4h, require funding-rate sign to favor our direction (we want to be receiving funding, not paying). Negative funding + LONG re-entry = green; negative funding + SHORT re-entry within 4h = red flag. Do not auto-apply.

3. **Complementary to rngpos hard-reject (decimal-token research):** both attack the chase-entry failure mode from different angles. rngpos has stronger off-the-shelf evidence (Mbanga 2022 + today's match); funding-direction needs our own backtest first. If only one implemented, prefer rngpos.

**Profit-ratio implication:** if funding-direction check had blocked today's BILL ×3 + UB + ALCH-reentry + BLUAI = +1.2 USDT saved. Day lifts ~+2.4 → ~+3.6 USDT. BUT overlaps with rngpos rule — independent lift estimated +0.3 to +0.7 USDT/day.

**Risk if applied wrong:**

- Treating funding-extreme as standalone signal → counter-trend entries in strong continuations → exact "shorts pile in get squeezed" outcome.
- Blanket "no entry against funding direction" → blocks legitimate breakouts against fading funding bias → reduces trade count.
- Mitigation: rule fires ONLY on re-entry within 4h, paired with Flipster 4-signal confirmation stack before any contrarian use.

### OI delta interpretation

**Established (cited across 4 sources — trdr.io docs, CryptoCred, Hyblock Academy, XT Exchange):**

1. **Canonical 4-quadrant map** (trdr.io official taxonomy, https://docs.trdr.io/key-features-and-indicators/sentiment-indicators/open-interest-open-interest-delta):

| Price | OI | Signal | Mechanic |
| --- | --- | --- | --- |
| ↑ | ↑ | **Trend continuation up** | New longs opening; conviction high |
| ↑ | ↓ | **Short-cover rally / fade risk** | Existing shorts closing, no fresh longs — mean-reverts |
| ↓ | ↑ | **Trend continuation down** | New shorts opening; bearish conviction |
| ↓ | ↓ | **Long capitulation / reversal proximate** | Longs closing, no fresh shorts — fuel exhausted |

2. **CryptoCred 50/50 caveat (must be respected — https://medium.com/@cryptocreddy/comprehensive-guide-to-crypto-futures-indicators-f88d7da0c1b5):** OI is *always* 50% long / 50% short (every contract has a buyer and seller). OI delta does NOT mean "more longs than shorts" — it means "aggregate positioning is changing." Combine with delta/CVD/funding to identify which side is aggressive.

3. **Breakout integrity rule (XT Exchange, https://medium.com/@XT_com/bitcoin-futures-market-microstructure-liquidation-cascades-funding-regimes-and-open-interest-978b107b4889):** *"a breakout accompanied by rising OI is structurally sound, while a breakout on falling OI is a liquidity grab and will likely mean-revert."* Cleanest off-the-shelf discriminator for chase-entry decisions.

4. **Consolidation + OI (Hyblock Academy, https://academy.hyblockcapital.com/indicators/orderflow-and-open-interest/open-interest):** High OI during consolidation → stops cluster on both sides → breakout amplifies into a liquidity cascade. Flat/falling OI during consolidation → no breakout fuel.

5. **Capitulation signal (Hyblock):** *"sharp price movement + OI drop leads to a reversal as trapped traders exit."*

**Speculative (label as such):**

- **No published % threshold for "significant" OI delta.** All four sources use qualitative language ("sharp", "large"). Empirical threshold must come from our own scatterplot.
- Whether `/fapi/v1/openInterest` 5-min granularity is fine enough for our 5–15 min scalp horizon — needs latency check before any rule.
- Whether decimal-priced perps follow the 4-quadrant map as cleanly as majors — thin books may make OI delta noisier. No source isolates small-cap subgroup.

**Today's empirical match (2026-05-11):**
- HUSDT-2 re-entry WIN vs UB/BILL re-entry LOSERS likely separable by OI-delta sign at re-entry time. UNVERIFIED — we do not currently log OI delta at entry.
- USELESSUSDT user 10x position (+$1.43 unrealized, MFE +1.56) profile = textbook Price↑+OI↑ fresh-long entry.
- SKYAI 80%-giveback exit captured a Price↑+OI↓ profit-take rally before it faded.

**Action recommendations (NO risk-param changes, user-decision queued):**

1. **Diagnostic-only first:** add `/fapi/v1/openInterest` 5-min delta to strategy-agent's pre-trade context. Log OI-delta sign + magnitude on every proposal. NO filter applied until ≥ 30 trades observed. Queue to error-fix-agent ONLY with explicit user OK.

2. **Speculative hypothesis (requires ≥ 30-trade evidence first):** on same-symbol re-entry within 4h, require OI-delta sign to confirm direction (LONG re-entry needs OI rising while price rising; SHORT re-entry needs OI rising while price falling). Negative-conviction quadrants → re-entry REJECTED. Do NOT auto-apply.

3. **Hierarchy if only one filter ships:** prefer **rngpos** (Mbanga 2022 + today's match — strongest evidence). OI-delta ranks 3rd behind funding-sign because it requires extra API call per proposal.

**Risk if applied wrong:**

- Treating Price↑+OI↓ as hard NO-LONG → misses legitimate squeeze-driven rallies that continue after short-cover-then-fresh-longs handoff. Mitigation: limit OI-delta filter to RE-ENTRY decisions only, not first entries.
- Coarse 5-min sampling → lag → adverse selection. Mitigation: verify 1-min granularity available before any rule implementation.

### Expectancy math

**Canonical R-multiple form (Van Tharp, via https://www.pnlledger.com/expectancy-r-multiples-the-plain-english-guide/):**
`Expectancy in R = p × AvgWinR + (1 − p) × AvgLossR`

Where:
- p = win rate
- AvgWinR = average R-multiple on winners (positive)
- AvgLossR = average R-multiple on losers (negative)
- 1R = the strict per-trade risk cap (for us: 0.50 USDT)

**Worked example for our system 2026-05-11:**
- avg_win = +0.567 USDT = +1.134R; avg_loss = −0.177 USDT = −0.354R; WR = 0.50
- E = 0.5(1.134) + 0.5(−0.354) = +0.39R = +0.195 USDT/trade
- Daily expectancy at 13 trades = +2.53 USDT (matches realized)

**Threshold guidance (LuxAlgo + Hyrotrader):**
- E < 0R: losing system, do not trade
- 0 to +0.2R: marginal edge, prone to drawdown
- +0.2 to +0.5R: solid working edge (where we are)
- > +0.5R: rare; usually indicates either (i) small sample size, (ii) overfitted backtest, (iii) hidden risk

Source: https://www.luxalgo.com/blog/win-rate-and-riskreward-connection-explained/

**Break-even by WR at fixed R:W:**
- At R:W = 1:1, BE WR = 50%
- At R:W = 1:2, BE WR = 33%
- At R:W = 1:3, BE WR = 25%
- At our R:W = 1:3.2 actual, BE WR = ~24% — we have very wide safety margin even at 50% WR. Our edge is robust.

**FEE-ADJUSTED expectancy under tightened max-loss (added 2026-05-12T00:00Z):**

Tightening max-loss from $0.50 → $0.10 **multiplies fee-burden-per-1R by 5x** because round-trip fees scale with notional ($3.5 × leverage) while 1R now scales with $0.10 not $0.50.

Binance regular taker = 0.045% per side → round-trip = 0.09% of notional. Source: https://www.binance.com/en/fee/futureFee, https://www.binance.com/en/blog/futures/421499824684902239.

| Lev | Notional | Round-trip taker fee | % of 1R ($0.10) | Fee-adj BE-WR |
| --- | --- | --- | --- | --- |
| 5x | $17.5 | $0.0158 | 15.8% | 27.6% |
| 8x | $28.0 | $0.0252 | 25.2% | 29.8% |
| 12x | $42.0 | $0.0378 | 37.8% | ~33% |
| 15x | $52.5 | $0.0473 | **47.3%** | **35.0%** |

**Post-fee expectancy by tier:** +0.36R at 5x, +0.30R at 8x, +0.20R at 15x (vs +0.39R zero-fee baseline). **High-leverage tiers are now LEAST profitable per trade after fees.** At a 13-trade day with all 15x: +$0.26/day; at all 5x: +$0.51/day.

**Safety margin shrunk:** at 1R=$0.50 the 15x BE-WR was 26% → 24-pp cushion vs our 50% WR. At 1R=$0.10 the 15x BE-WR is 35% → 15-pp cushion. **Cushion halved overnight**; system still profitable but more fee-sensitive.

**Action recommendations (NO risk-param changes; queued for user OK):**
- Diagnostic: log `fee_burden_pct_of_1R` on every proposal + journal entry.
- Maker-preference on noisy 12-15x entries (rngpos ≥ 60% intra-1m) to save ~50% of entry-side fee.
- Display "edge after fees" per leverage tier in `/status` / daily-report.

**Risk if applied wrong:**
- Maker-only entries miss fills on fast scalps → fix is selective application, not blanket switch.
- User over-anchors on raw fee % and rejects still-positive 15x trades → pair fee % with post-fee E-in-R.
- VIP/BNB discount not factored — verify user fee tier; real burden may be ~10% lower than tabulated.

### Session edge

**Established (cited):**

1. **22:00–00:00 UTC long-bias window in BTC.** Quantpedia (Gemini hourly data 2015-10-09 to 2022-02-03): 22:00–23:00 UTC hours are the most statistically significant positive returns (5% level). A naive long-at-22:00 / exit-at-00:00 UTC strategy yields **33% annualized return, Sharpe 1.58, max DD −34%, ann. vol 20.93%**. Coincides with the window when NYSE, London, Continental Europe, Tokyo, and HK are all simultaneously closed → retail/algo-native flow dominates. Sources: https://quantpedia.com/strategies/intraday-seasonality-in-bitcoin, https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin/

2. **"Monday Asia Open Effect" (Concretum, 2018–2025).** Sunday ~23:00 UTC (Tokyo open) to Monday ~23:00 UTC carries strongly positive returns for an intraday trend-following portfolio. **Gross Sharpe ≈ 1.6** for the trend version vs ~0.8 for vol-targeted long-only at 20% ann. vol target. Effect strengthened post mid-2020 with institutional participation. Source: https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/

3. **Worst-window (caution flag, not statistically significant):** 03:00–04:00 UTC has the worst sample returns in Quantpedia's study; insignificant at 5% level. Directional avoid signal, not a hard sell. Source: https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin/

4. **Turn-of-the-candle micro-effect.** arXiv 2402.11930: positive +0.58 bps/min concentrated at minutes 0/15/30/45 of each trading hour; other minutes average negative. Detected mid-2020 onward; attributed to algorithmic execution rhythms. Source: https://arxiv.org/html/2402.11930v2

5. **Asia session general character:** lower volume, narrower ranges, more sideways action during major US/EU off-hours — except for the documented late-UTC window above. Industry-consensus context, not a backtest. Source: https://medium.com/@mzain10/why-asian-new-york-and-london-times-matter-in-crypto-trading-c00ad9dfe8e9

**Speculative (label as such):**

- Whether the BTC 22:00–00:00 UTC long-bias transfers to small-cap decimal alts (BILL, UB, NAORIS, SAGA, SKYAI tier) at our 5–15 min scalp horizon — UNTESTED. Likely directional carry via beta-to-BTC; magnitude unknown.
- Whether the effect is symmetric for shorts (Quantpedia is long-only; no documented short-side reversal in same window).
- Whether the Concretum Sharpe-1.6 trend portfolio survives transaction costs / slippage on Binance USDT-M perps at our horizon.
- Whether our own trade-events.jsonl shows the same hour-of-day skew on actual fills — not currently bucketed by entry hour.

**Action recommendations (NO risk-param changes, user-decision queued):**

1. **Diagnostic script `scripts/analyze_entry_hour_pnl.py`** — read `data/trade-events.jsonl` + closed-trade journal, bucket realized PnL and win-rate by entry hour-UTC + day-of-week, output heatmap-style table. Pure observation. Queue to error-fix-agent ONLY with user OK.

2. **Lowest-effort first step:** add `entry_hour_utc` and `entry_session` (Asia / EU / NY-overlap / Late-NY-Off) fields to trade-journal records going forward. Non-risk-touching. Queue for user OK.

3. **Speculative hypothesis (requires ≥ 50 closed trades bucketed by hour before any approval):** if scatterplot confirms BTC pattern carries to alts, add a +0.02 confidence NUDGE (not a hard filter) for LONG proposals in 22:00–00:00 UTC and a −0.02 nudge for LONG proposals in 03:00–05:00 UTC. Stays inside the 0.75 min-confidence gate. Do NOT auto-apply.

**Profit-ratio implication:** If half the BTC late-UTC tilt carries to our alts, ~5-pp WR bump on the ~30% of trades in the window adds roughly +0.15–0.30 USDT/day. Material but small; complementary to rngpos / funding-sign / OI-delta filters from prior research. Does NOT independently close the gap to $10/day.

**Risk if applied wrong:**

- Over-fitting BTC-major pattern to small-cap alts → confidence-bonus fires on losing setups → degrades selection. Mitigation: backtest first, nudge-not-filter, LONG-only (literature is asymmetric).
- Sample-period drift: 22:00–00:00 UTC window strengthened post-2020 with algo flow; could weaken if regime rotates. Mitigation: re-validate on rolling 90-day window if implemented.
- Conflating session-edge with algo-execution-edge (arXiv 2402.11930 turn-of-candle): if our edge is actually the minutes-0/15/30/45 micro-effect, the hour-of-day signal is a coarse proxy and fragile.

### Cry-wolf / alarm fatigue in monitoring pipelines

**Established (cited):**

1. **Google SRE rule (Beyer et al., O'Reilly 2016):** *"Every page response should require intelligence. If a page merely merits a robotic response, it shouldn't be a page."* Operational test: every alert must answer YES to "can I take action in response to this?" If NO, the alert must auto-resolve upstream or be suppressed. Sources: https://sre.google/sre-book/monitoring-distributed-systems/, https://sre.google/sre-book/being-on-call/

2. **30% operator-ignore rate** at overload volume (IDC via Stamus). **~32 min investigator-time cost per false positive.** **51% of SOC teams overwhelmed; 25% of analyst time on FPs** (Trend Micro 2024 via IBM). **"Tenth-alarm threshold"** — operator urgency fades at ~10 consecutive false alarms (Crytica). Sources: https://www.stamus-networks.com/blog/the-hidden-risks-of-false-positives-how-to-prevent-alert-fatigue-in-your-organization, https://www.ibm.com/think/topics/alert-fatigue, https://www.cryticasecurity.com/blog/false-positives-and-alert-fatigue-what-you-need-to-know

3. **Trading-specific gap (Tyler Capital HRO study, PMC 8978471):** algorithmic-trading firms have a documented response-time gap (alert in microseconds, human kill-switch in ~30 min) but the cry-wolf failure mode is *not* explicitly addressed in the trading-research literature — confirmed as an *understudied* dimension that crosses over from healthcare/SOC. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC8978471/

4. **Canonical mitigations: deduplication windows, actionability gating, severity tiering, suppression with severity-upgrade exception** (cross-source consensus across IBM, Stamus, Google SRE).

**Today's empirical match (2026-05-12):** 7 EXIT_EARLY verdicts from loss-research agent all blocked by missing `scripts/run_close_position.py`. Count is at 70% of the canonical 10-alarm desensitization threshold within a single session. Direct textbook cry-wolf failure mode.

**Action recommendations (NO risk-param changes; pipeline hygiene only):**

1. Phase 1 fix already queued: ship `scripts/run_close_position.py` → makes EXIT_EARLY verdicts actionable.
2. Add 10-min dedup window to loss-research-agent output keyed on (symbol, position_id), with severity-upgrade exception (worse r_curr = fresh fire).
3. Add "verdicts-blocked-by-missing-tool" counter to `/status` output.
4. Adopt actionability gate as code-review rule: every verdict-emitting agent must have a named existing execution path OR `advisory_only=true` tag.

**Risk if applied wrong:** over-suppression masks fast-deteriorating positions; converting cry-wolf to actionable amplifies any verdict-quality issues. Mitigation: log every executed EXIT_EARLY's t+30min PnL to monitor false-positive *verdict* rate before they accumulate.

### Pause-scope / graded kill switch (carry-over pause UX)

**Established (cited):**

1. **Binance Futures' own risk system ships the two-mode pattern.** When exchange-level quantitative-rule limits trip, the account transitions to reduceOnly-only state, NOT a full halt: *"Futures Trading Quantitative Rules violated, only reduceOnly order is allowed... please reduce the position."* New positions are blocked; existing-position protective management continues to function. Source: https://developers.binance.com/docs/derivatives/usds-margined-futures/error-code

2. **Cross-market circuit breakers preserve stop-loss orders during halts.** Stop-loss orders remain pending — the halt suspends matching, NOT the protective layer. Source: https://bookmap.com/blog/trading-circuit-breakers-and-halts-how-they-protect-markets-and-what-traders-should-know

3. **NYIF "Panacea or Pandora's Box?" frames binary kill switches as the riskier design.** *"Market participants and regulators have debated the need for multi-level kill switches..."* — graded responses are the regulator-debated alternative. Source: https://www.nyif.com/articles/trading-system-kill-switch-panacea-or-pandoras-box

4. **LuxAlgo taxonomy: stop-loss layer and kill-switch layer are parallel, not nested.** *"Stop-loss rules automate exits to minimize losses, while emergency controls employ kill switches and circuit breakers for major disruptions."* Source: https://www.luxalgo.com/blog/risk-management-strategies-for-algo-trading/

5. **Reduce-only as a settled primitive across all major exchanges** (Bybit, Binance, Bitunix). Source: https://www.bybit.com/en/help-center/article/Reduce-Only-Order

**Today's empirical match (2026-05-12 night):** safety pause spanning 6+ hours blocked BE-trail on FHE (r=+1.0) and BUSDT (r=+1.14); USELESSUSDT swung $14 with no algorithmic intervention. Direct give-back-prevention loss tonight.

**Action recommendations (NO risk-param changes; user-decision queued for `error-fix-agent` spawn):**

1. Add `PAUSE_MODE` enum: `PAUSE_NEW_FIRES_ONLY` (NEW default), `PAUSE_FULL_HALT` (retained for explicit emergency-shutdown), `PAUSE_REDUCE_ONLY_ALL` (reconciler-disagreement / state-mistrust).
2. Whitelist in `PAUSE_NEW_FIRES_ONLY`: BE-trail SL tighten, R-lock SL tighten, giveback-exit reduce-only close, loss-research EXIT_EARLY reduce-only close, watcher status/journal writes.
3. Default consecutive-losses-3 and daily-loss-trip routes to `PAUSE_NEW_FIRES_ONLY`, NOT full halt.
4. `/status` must surface current PAUSE_MODE + allow-list in plain English.
5. Pause-transition handler must drain in-flight orders before flipping mode.

**Risk if applied wrong:**
- Over-permissioning → stale-data-driven SL move could close wrong; mitigation: price-validation guard (ERROR-20260511-4) is a hard prerequisite.
- Under-permissioning → cry-wolf re-emerges; mitigation: include all four protective rules, not a subset.
- Order-of-operations race during transition → drain in-flight orders first.

**Profit-ratio implication:** +$0.5–1.5/week from giveback-prevention alone; structurally unblocks ~3 of 19 queued enhancement findings (R-trail deployment, loss-research EXIT_EARLY action path, BE-trail-during-pause).

### News catalysts

**Established (cited, multi-source-corroborated):**

1. **Token-unlock fade is the strongest scheduled-event edge in crypto, with two-tier empirical confirmation.** Keyrock analysed **16,000+ unlock events** and found **90% produce negative price pressure**, decline begins **30 days before** the unlock, accelerates in the final week, **peak negative impact concentrates 2 days BEFORE** the unlock (Yellow.com), and unlock day itself is muted while **secondary impact emerges 3-4 days post-unlock**. Stabilisation ~14 days post. Sources: https://crypto.news/token-unlocks-almost-always-negative-for-price-keyrocks-study-reveals/, https://beincrypto.com/keyrock-research-token-unlocks/, https://cryptoslate.com/90-of-token-unlocks-drive-prices-down-declines-begin-a-month-ahead/, https://yellow.com/learn/token-unlocks-explained-how-vesting-schedules-impact-crypto-prices-and-market-liquidity

2. **Magnitude scales non-linearly with size, and recipient class matters.** Keyrock: large unlocks (5-10% of float) drop **2.4× steeper** than medium (1-5%). **Team unlocks crash worst at -25%.** Investor/private unlocks ≈ team profile. **Ecosystem unlocks are the only positive class (+1.18%)** because they fund infrastructure/incentives, not sell pressure. Filter implication: tradeable unlock = `size ≥ 1% of float AND recipient ∈ {team, investor, private}`.

3. **Binance new-listing fade is documented at industrial scale.** CryptoNinjas + Storible joint study (Feb 2025, **389 tokens** across 6 CEXs): **98% of Binance-listed tokens eventually dump** from listing price. **Average initial pump = +87%; average post-listing decline = −70% from listing peak.** **46% of tokens print ATH at listing** and never surpass it. Source: https://bitpinas.com/cryptocurrency/binance-token-listing-dump/

4. **Optimal trade-side asymmetry by event window** (Yellow.com explicit): *"best entry point for long positions occurs 14 days AFTER significant unlocks once volatility settles, while optimal exit timing is 30 days BEFORE major unlocks when hedging activity typically begins."* Translation for our context-filter use: T-30d → T-2d = SHORT-bias / NO-LONG. T+0 → T+14d = SHORT-bias continuing (secondary selling 3-4d post). T+14d onward = neutral / LONG eligible again.

**Today's empirical match (2026-05-12 night):** Agency has NO calendar-layer data currently. 22 enhancement findings queued and ONDO at 0.83 flagged "readiest setup for resume" — but no check on ONDO unlock calendar or recent listing announcements has been done. The unverifiable cost of NOT having this layer: any LONG fire on a token in its T-30d unlock window is statistically into a headwind we can't see.

**Speculative (label as such):**
- Whether 5-15 min scalp horizon captures the daily/weekly bias documented in the literature — possibly fractional, needs own data.
- Whether decimal-priced small-cap perps follow the same magnitude as top-100 spot tokens — likely directional carry, magnitude unknown.
- Whether Binance USDT-M *perp* listings (vs spot listings) follow the same 98%-dump pattern — perps have shorts day-1; could compress timeline. Needs separation in own data.
- Whether our 5-symbol scanner universe even contains tokens in their unlock window often enough to matter — could be < 10% of trades affected.

**Mapping to locked policy (context-filter, NOT risk-param change):**

- LONG proposal on token in T-7d unlock window (size ≥ 1% float, team/investor recipient): confidence ceiling **−0.05** (0.78 nominal → 0.73 effective → BLOCKED by 0.75 gate).
- SHORT proposal on same token: confidence floor **+0.02** (0.73 nominal → 0.75 effective → GREEN).
- Token in first 24h post-Binance-listing: **hard NO-LONG**; SHORT only on retest of listing-day high.
- No change to margin (3.5), leverage (2-15x), max-loss ($0.10), daily-cap ($1.0), max-open (8), min-conf (0.75).

**Action recommendations (NO risk-param changes, user-decision queued):**

1. **Diagnostic-first: `data/calendar-layer.json`** snapshot via daily cron pulling Tokenomist or DropsTab API (next-30d unlocks for our top-100 watch universe, fields: `symbol`, `unlock_date`, `unlock_pct_of_float`, `recipient_class`) + Binance announcements RSS (last 30d listings, fields: `symbol`, `listing_date`, `listing_type`). Pure observation infrastructure. Queue to error-fix-agent ONLY with user OK.

2. **After ≥ 30 trades with calendar data attached, scatterplot bias-vs-outcome.** If documented effect is ≥ 0.5σ visible in our own data, THEN propose the confidence-nudge filter above. Until then, **observe only**.

3. **Immediate (one-time, manual) use for tonight's ONDO resume decision:** check tokenomist.ai for next-14d ONDO unlocks AND Binance announcements page for ONDO listing date before firing. No code change.

4. **NOT recommended:** auto-rejecting on any unlock window without our own data. Literature is on top-100 spot; imposing blindly could over-cut trade count and break the +$2.5-5/day edge.

**Profit-ratio implication (quantified hypothesis, label needs-validation):**

If 10% of daily trades face documented calendar headwind and filter avoids bottom-quartile of those: expected lift ~$0.20-0.40/day. Independence from rngpos / funding / OI signals likely high (different signal class — calendar vs. microstructure). Combined with other queued filters, lifts realistic ceiling from ~$2.5-5/day to ~$3-5.5/day on 30 USDT wallet. Does NOT independently close gap to $10/day.

**Risk if applied wrong:**
- Over-fitting top-100 spot pattern to small-cap perps → could block highest-edge setups. Mitigation: 30-trade observation FIRST, no auto-rule.
- Stale calendar API data → wrong-window decisions. Mitigation: staleness check (data ≤ 24h) before any rule fires.
- Compounding with rngpos + funding + OI filters could compress trades from ~13/day to ~5/day. Mitigation: stage filter rollout one at a time, measure delta after each.

### Volatility sizing

**Established (cited, multi-source):**

1. **Canonical formula:** `Position Size = Account Risk / (ATR × Multiplier)` — consensus across LuxAlgo, FXNX, Setup4Alpha. LuxAlgo claims **25% drawdown reduction** vs fixed-percentage sizing during volatile periods (multi-asset, no specific window cited — directional evidence). Sources: https://www.luxalgo.com/blog/5-position-sizing-methods-for-high-volatility-trades/, https://setup4alpha.substack.com/p/how-to-implement-volatility-adjusted, https://fxnx.com/en/blog/atr-based-position-sizing-mastering-volatility-anti-fragile

2. **Multiplier for short-timeframe (FXNX explicit):** 1.5× ATR = aggressive scalping (tight stops + spike risk); 2.0×-2.5× ATR = "sweet spot, clears daily noise"; 3.0×+ = swing only. For our 5-15 min horizon: **1.5×-2.0× ATR(14, 5m)** is literature-aligned.

3. **Leverage-substitution principle (FXNX numeric example):** when ATR doubles, lot-size halves to preserve constant $-risk. For fixed-margin systems like ours, this re-expresses as `effective_leverage = min(confidence_tier, ATR_cap)`. Margin stays 3.5, 1R stays $0.10, leverage flexes inversely with realized volatility.

4. **Timeframe-match rule (FXNX):** "Never use a 5-min ATR to set a stop for a 3-day trade" — symmetric: never use 1h ATR for a 5-15 min scalp. Correct period for our setup: **ATR(14) on the 5-min candle**, recomputed at proposal time. Staleness check: data ≤ 2 candles old.

5. **Scalp-fit caveat (LuxAlgo):** scalping is the **weakest fit** for ATR-systems because 5-min ATR contains microstructural noise. Therefore ATR-cap must be a SOFT overlay (de-escalates leverage), not a HARD reject.

**Speculative (label as such):**

- Whether decimal-priced perp ATR-as-%-of-price displays the same regime structure as majors. Prior penny-anomaly research suggests tick-size-%-of-price is structurally higher on decimal coins → ATR-%-of-price likely also inflated → blanket cap could over-de-leverage our highest-volume cohort. No published study isolates Binance USDT-M decimal-perp ATR distributions.
- Whether ATR(14) vs ATR(7) vs ATR(20) is optimal at our 5-15 min hold horizon. 14 is conventional anchor; no scalp-specific peer-reviewed evidence.
- Whether LuxAlgo's "25% DD reduction" transfers to a fixed-margin system flexing *leverage* rather than *quantity*. The math is equivalent on paper, but margin-call dynamics and liquidation distances differ between the two levers.

**Proposed ATR-cap overlay (5-tier, NOT risk-param change):**

| ATR(14, 5m) as % of price | Max allowed leverage |
| --- | --- |
| ≤ 1.0% | full ladder (up to 15x) |
| 1.0%-2.0% | cap at 8x |
| 2.0%-3.0% | cap at 5x |
| 3.0%-4.0% | cap at 3x |
| ≥ 4.0% | cap at 2x (or NO-TRADE per FXNX "avoid leverage entirely if ATR > 3%") |

`effective_leverage = min(ladder_from_confidence, ATR_cap_from_volatility)`. Confidence ladder unchanged. Margin 3.5 unchanged. 1R = $0.10 unchanged. Existing tighter-SL step-down rule remains in parallel.

**Action recommendations (NO risk-param changes; user-decision queued):**

1. **Diagnostic-first: `scripts/analyze_atr_vs_outcome.py`** — read `data/trade-events.jsonl` + journal, compute ATR(14, 5m) at entry per symbol via `/fapi/v1/klines`, bucket realized PnL × win-rate by ATR-bucket × leverage-tier × confidence-tier. Pure observation. Queue to error-fix-agent ONLY with user OK.

2. **Add `atr_pct_at_entry` field to trade-journal records.** Non-risk-touching infrastructure. Required for #1 and any future threshold.

3. **Speculative hypothesis (requires ≥ 30 trades with ATR-attached):** if scatterplot shows high-ATR × high-leverage trades cluster in negative-EV quadrant, propose ATR-cap overlay above. Do NOT auto-apply.

4. **NOT recommended:** auto-applying ATR cap before our own data confirms. The scalp-noise caveat means naive cap could over-de-leverage on transient micro-spikes.

**Profit-ratio implication (hypothesis, needs-validation):** If overlay catches worst-10% trades by ATR-mismatch and converts to no-trades: ~+$0.10-0.20/day expected lift. Independence from rngpos/funding/OI/news-calendar signals is HIGH (different signal class). Primary value is drawdown smoothing, NOT return enhancement — aligns with LuxAlgo's 25%-DD-reduction framing. Does NOT independently close gap to $10/day.

**Risk if applied wrong:**

- Over-de-leverage on routine micro-spikes → starves high-edge setups. Mitigation: use ATR(14) averaged, not raw 5-min realized range.
- Decimal-token systematic bias → cap blanket-de-leverages highest-volume cohort. Mitigation: bucket diagnostic by price-tier first; consider price-tier-conditional cutoffs.
- Stale ATR data → exactly the FXNX-warning bug. Mitigation: 2-candle staleness check.
- Compounding with rngpos + funding + OI + news + ATR → could compress trade count from ~13/day to ~4/day. Mitigation: staged rollout, measure delta after each.

### Regime classification

**Established (cited, multi-source-corroborated):**

1. **Canonical practitioner taxonomy = 2×2 matrix (trend-direction × volatility-state) → 5 regimes** (LuxAlgo + QuantMonitor + Thrive convergent): `UP_LOWVOL`, `UP_HIGHVOL`, `DOWN_LOWVOL`, `DOWN_HIGHVOL`, `RANGE` (FLAT trend). Sources: https://www.luxalgo.com/blog/market-regimes-explained-build-winning-trading-strategies/, https://quantmonitor.net/how-to-identify-market-regimes-and-filter-strategies-by-trend-and-volatility/, https://thrive.fi/blog/trading/crypto-market-regime-detection

2. **Computable thresholds (Thrive, explicit):**
   - **ADX**: < 20 = range, 20-40 = developing, > 40 = strong trend, > 60 = exhaustion-watch.
   - **ATR-percentile (252-period lookback)**: < 0.20 = low-vol; 0.20-0.80 = normal; > 0.80 = high-vol.
   - **MA slope (20-period)**: < 0.005 + MA separation < 0.02 = ranging; > 0.02 = uptrend; < -0.02 = downtrend.
   - **Bollinger Band Width**: low = squeeze (breakout imminent); high = elevated volatility.

3. **QuantMonitor backtest filter result** (trend × vol matrix applied as strategy on/off switch): trend-following strategy active ~95% of bars in `Up_LowVol`, ~59% in `Up_MidVol`/`Up_HighVol`, 0% in all `Down_*` regimes. Demonstrates that **regime-aware on/off gating concentrates strategy activity in the highest-edge quadrants** without changing the strategy itself.

4. **LuxAlgo quoted impact** (multi-asset, daily/4h, NOT 5-15 min crypto): regime-aware strategy switching delivers **+10-30% risk-adjusted return improvement**, drawdown cut by similar margin. One cited HMM strategy: 36% return / Sharpe 1.7 / max DD 7.3%. **Transfer to our 5-15 min decimal-perp horizon is UNVERIFIED.**

5. **Per-regime strategy adjustments (Thrive):**
   | Regime | Position Sizing | Stop Placement | Entry Method |
   | --- | --- | --- | --- |
   | Trending | 100% | swing lows/highs | MA pullback |
   | Ranging | 50-75% | beyond boundaries | S/R touch |
   | Volatile | 25-50% or flat | wide or none | extreme readings only |

6. **HMM-based regime detection is the academic state-of-the-art** (Preprints.org Bitcoin 2024-2026, https://www.preprints.org/manuscript/202603.0831): 3-state (low/high/distress) and 5-state Bitcoin volatility-clustering models cited optimal. **NOT recommended for our wallet size** — too much code surface; 2×2 matrix captures most available signal.

**Speculative (label as such):**

- Whether 5-15 min ATR-percentile transfers cleanly to small-cap decimal-priced perps. Decimal coins likely fat-tailed ATR-%-of-price → 80th percentile may be loose. Needs per-symbol percentile, not blanket.
- Whether SMA-50 on 5-min candles (4.2-hour anchor) is fast enough to label regime at scalp entry. Whipsaw risk on faster MAs; lag on slower MAs.
- Whether our existing `rngpos` feature collinearly captures most of the range-vs-trend information ADX would add.
- Whether ranging regime's quoted 80-85% WR is realistically achievable at our R:W ≈ 1:3.2 — most cited ranging strategies use R:W ≤ 1:1.5.

**Mapping to locked policy (diagnostic-only tag, NOT a filter or risk-param change):**

- Add `regime_at_entry` field to trade-journal records (one of: `UP_LOWVOL | UP_HIGHVOL | DOWN_LOWVOL | DOWN_HIGHVOL | RANGE`).
- Computed at proposal-time from Binance 5-min klines:
  - `trend_sign`: sign of `(SMA(50)[0] - SMA(50)[5])` — LONG/SHORT/FLAT (FLAT when abs slope < 0.05% of price).
  - `vol_state`: percentile rank of `ATR(14)/Close` over last 252 candles. LOW < 20th, NORMAL 20-80, HIGH > 80th.
  - Combine: trend × vol → 4 quadrants; FLAT → `RANGE` regardless of vol.
- NO filter, NO confidence nudge, NO risk-param change. Margin 3.5 / leverage 2-15x / max-loss $0.10 / daily-cap $1.0 / max-open 8 / min-conf 0.75 all UNCHANGED.

**Action recommendations (NO risk-param changes; user-decision queued):**

1. **Diagnostic-first: `regime_at_entry` field** via `scripts/regime_tag.py` invoked from proposal pipeline. Tag written to trade-journal + proposal context. Non-risk-touching. Queue to error-fix-agent ONLY with explicit user OK.

2. **After ≥ 30 tagged trades, scatterplot WR × regime × strategy-type.** Hypothesis: breakout/momentum strategies cluster wins in `UP_HIGHVOL`, losses in `DOWN_HIGHVOL`/`RANGE`. If confirmed, next stage is regime × strategy-type confidence NUDGE table — NOT a hard filter.

3. **Optional: `/status` displays current `regime_at_entry` for BTC** as a glance-readable crypto-wide regime indicator.

4. **NOT recommended:** auto-rejecting any proposal based on regime; LuxAlgo numbers are daily/4h multi-asset, direct transfer unverified.

5. **NOT recommended:** HMM/ML regime classifier. Too much code surface for wallet size.

**Profit-ratio implication (hypothesis, needs-validation):** If regime tagging surfaces a single high-loss-rate quadrant accounting for ~25% of trades, and a future filter rejects/de-weights that quadrant: ~+$0.10-0.30/day expected lift after ≥ 30-trade calibration. Independence from rngpos/funding/OI/news-calendar/ATR signals is MEDIUM — vol-state correlates with ATR overlay, trend-sign is orthogonal. Primary value: **diagnostic visibility (currently zero)**, not immediate return enhancement. Does NOT independently close gap to $10/day.

**Risk if applied wrong:**

- Tagging-only is safe; no execution risk.
- Threshold drift on decimal-perp ATR percentile → mitigation: per-symbol percentile bucket, not cross-symbol.
- SMA-50 lag → mitigation: pair with EMA(20) cross confirmation, or downgrade trend conf when EMA-20 < SMA-50 in UP_*.
- Premature filter adoption by future contributor → mitigation: explicit "diagnostic-only, no filter until N=30" comment in code path.

## Sources known reliable (rotate to avoid same-source bias)

- @CryptoCred (TA threads)
- @TraderXO (futures structure)
- @SmartContracter (W/M patterns)
- @WClementeIII (on-chain context)
- @rektcapital (cycle work)
- Glassnode Insights (on-chain weekly)
- Delphi Digital (research notes)
- Messari (sector reports)
- The Block Research (data pieces)
- Binance Academy (foundational articles)
- Books: "Trading in the Zone" (Douglas), "Reminiscences of a Stock Operator" (Lefèvre), "Way of the Turtle" (Faith), "Trading and Exchanges" (Harris)
- Academic: arXiv "quantitative finance" + "market microstructure"

## Sources to AVOID
- Paid-pump signal channels
- Generic "secret strategy" YouTube content
- Anything without a verifiable source or backtest
