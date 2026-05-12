# Strategy Research Log

Chronological output from `strategy-research-agent`. Each fire appends one entry.

Topic-organized current state lives in `agents/strategy-research-agent/memory.md`.

---

## RESEARCH-2026-05-12T21:30:00Z

**Question (queue item #1, on-rotation):** Within our locked fixed-margin policy (3.5 USDT per slot, $0.10 strict max-loss, 2-15x leverage), how should ATR-based volatility-adjusted sizing translate? We can't change MARGIN per slot, but we CAN flex (a) the chosen leverage tier, and (b) the SL distance — so the actionable lever is "scale leverage and stop-distance inversely with ATR to preserve constant 1R = $0.10". Is there published evidence this beats fixed-leverage-by-confidence under our constraints?

**Sources reviewed:**
- LuxAlgo, "5 Position Sizing Methods for High-Volatility Trades" — https://www.luxalgo.com/blog/5-position-sizing-methods-for-high-volatility-trades/
- FXNX, "ATR-Based Position Sizing: Mastering Volatility (Anti-Fragile)" — https://fxnx.com/en/blog/atr-based-position-sizing-mastering-volatility-anti-fragile
- Setup4Alpha (Substack), "How to Implement Volatility-Adjusted Position Sizing" — https://setup4alpha.substack.com/p/how-to-implement-volatility-adjusted
- BingX Learn (search snippet, corroborating), "What is Average True Range (ATR) Volatility Indicator in Crypto Trading" — https://bingx.com/en/learn/article/what-is-average-true-range-atr-volatility-indicator-in-crypto-trading

**Key finding (single strong idea):** **For a FIXED-MARGIN system like ours, the canonical "position-size = risk / (ATR × multiple)" formula re-expresses as a LEVERAGE-and-STOP-distance rule.** Specifically: keep margin = 3.5 USDT constant, keep 1R = $0.10 constant, and let the quantity-of-asset (which determines per-tick PnL) flex with ATR. Mechanically this means **leverage tier should be chosen as a function of *current ATR-as-%-of-price*, not solely as a function of confidence**. Our current ladder is confidence → leverage; the literature-supported addition is `effective_leverage = min(confidence_tier, ATR_cap)` where ATR_cap forces lower leverage when realized volatility is high.

**Established (cited, multi-source-corroborated):**

1. **Core formula (LuxAlgo + Setup4Alpha + FXNX consensus):** `Position Size = Account Risk / (ATR × Multiplier)`. LuxAlgo quantifies a **25% drawdown reduction** for ATR-sizing vs fixed-percentage sizing during volatile periods (no specific window cited, but multi-asset). Setup4Alpha: equity curve "slightly smoother" on mean-reversion; no Sharpe/drawdown numbers given — directional, not quantitative. Sources: https://www.luxalgo.com/blog/5-position-sizing-methods-for-high-volatility-trades/, https://setup4alpha.substack.com/p/how-to-implement-volatility-adjusted

2. **Multiplier guidance for short-timeframe trading (FXNX explicit):** *"1.5× ATR — best for aggressive scalping, tighter stops, larger lot sizes, spike risk increases. 2.0×-2.5× ATR — sweet spot, generally enough to clear daily noise. 3.0×+ — swing trading."* For our 5-15 min scalp horizon: **1.5×-2.0× ATR on the 5-min or 15-min candle is the literature-aligned range.** Source: https://fxnx.com/en/blog/atr-based-position-sizing-mastering-volatility-anti-fragile

3. **Leverage-substitution principle (FXNX explicit numerical example):** *"When ATR doubles, lot size halves to preserve constant dollar risk."* For us: same-margin-but-different-leverage is the equivalent flex. A 2× ATR rise should drop chosen leverage by ~50%. Example: a 0.85-confidence proposal that would normally fire at 5x (per ladder) on a coin showing ATR(14, 5m) = 1.5% of price could be capped at 3x if ATR(14, 5m) ≥ 3% — preserving 1R at $0.10 with a wider, less-noise-triggered SL.

4. **Critical timeframe-match caveat (FXNX):** *"Never use a 5-minute ATR to set a stop for a trade you plan to hold for three days."* Symmetric: never use 1-hour ATR for a 5-15 min scalp. **For our system the correct period is ATR(14) on the 5-min candle**, recomputed at proposal-time. Cross-confirmed by BingX search snippet.

5. **Scalp-fit caveat (LuxAlgo + general consensus):** Scalping is **the weakest fit** for ATR-based systems because very-low-timeframe ATR contains microstructural noise and false volatility shifts. Implication: ATR-cap should be a SOFT overlay (de-escalates leverage) rather than a HARD reject filter. Source: https://www.luxalgo.com/blog/5-position-sizing-methods-for-high-volatility-trades/

**Speculative (label as such — needs our own backtest):**

- Whether decimal-priced perp ATR-as-%-of-price displays the same regime structure as majors. Tick-size-as-%-of-price is already known to be higher on decimal tokens (per our prior penny-anomaly research) — ATR-as-%-of-price could be systematically inflated, biasing the ATR-cap toward over-de-leveraging. **No published study isolates Binance USDT-M decimal-perp ATR distributions.**
- Whether ATR(14, 5m) is fine-grained enough vs ATR(7, 5m) or ATR(20, 5m) for our 5-15 min hold horizon. No source nails the optimum; 14 is the conventional anchor.
- Whether the LuxAlgo "25% drawdown reduction" carries to a fixed-margin system where the lever is *leverage* not *quantity*. The math is equivalent on paper, but exchange-side effects (margin-call dynamics, liquidation distance) differ between flexing quantity vs flexing leverage.

**Mapping to our locked policy (context-filter, NOT risk-param change):**

Current ladder (confidence → leverage):
| Confidence | Lev | Required R:R |
| --- | --- | --- |
| 0.75-0.79 | 2x | ≥ 2.0 |
| 0.80-0.84 | 3x | ≥ 2.0 |
| 0.85-0.89 | 5x | ≥ 2.5 |
| 0.90-0.94 | 8x | ≥ 3.0 |
| ≥ 0.95 | 15x | ≥ 3.5 |

**Proposed ATR-cap overlay** (added column, no removal of existing rules):
| ATR(14, 5m) as % of price | Max allowed leverage |
| --- | --- |
| ≤ 1.0% | full ladder (up to 15x) |
| 1.0%-2.0% | cap at 8x |
| 2.0%-3.0% | cap at 5x |
| 3.0%-4.0% | cap at 3x |
| ≥ 4.0% | cap at 2x (or NO-TRADE per FXNX "avoid leverage entirely if ATR > 3%") |

`effective_leverage = min(ladder_from_confidence, ATR_cap_from_volatility)`. Margin stays 3.5; 1R stays $0.10; SL distance scales with ATR; quantity falls out arithmetically. Existing "tighter-stop-step-down" rule remains a separate safeguard.

**Action recommendations (NO risk-param changes auto-applied, user-decision queued):**

1. **Diagnostic-first: `scripts/analyze_atr_vs_outcome.py`** — read `data/trade-events.jsonl` + closed-trade journal, compute ATR(14, 5m) for each symbol at entry time (Binance `/fapi/v1/klines`), bucket realized PnL and win-rate by ATR-bucket × leverage-tier × confidence-tier. Pure observation. **Queue to error-fix-agent ONLY with user OK.**

2. **Add `atr_pct_at_entry` field to trade-journal records going forward.** Non-risk-touching. Required for any future evidence-based threshold.

3. **Speculative hypothesis (requires ≥ 30 trades with ATR-attached, before any approval):** if scatterplot shows trades fired at high-ATR × high-leverage cluster in the negative-EV quadrant, propose the ATR-cap overlay above. **Do NOT auto-apply.** The 25% drawdown reduction in LuxAlgo is from equity-trading research; magnitude on our setup unknown.

4. **Lowest-effort first step (non-risk):** log ATR(14, 5m) and ATR-as-%-of-price on every proposal regardless of whether it enters the trade. Costs one extra `/fapi/v1/klines` call per proposal; produces the dataset for #3.

5. **NOT recommended:** auto-applying the ATR cap before our own data confirms it. The 5-min-ATR-noise caveat from LuxAlgo means a naive cap could over-de-leverage during routine micro-spikes and starve us of high-edge setups.

**Profit-ratio implication (quantified hypothesis, label needs-validation):**

If the ATR-cap overlay catches even the worst-10% trades by high-ATR-mismatch and converts them from −$0.10 losers to no-trades, expected lift on a 13-trade day ≈ +$0.10-0.20/day (1.3 trades × $0.10 avoided). Independence from rngpos / funding / OI / news-calendar signals is HIGH (different signal class — volatility vs price-action vs flow vs calendar). Combined with other queued filters, lifts realistic ceiling from ~$3-5.5/day to ~$3.2-5.7/day. **Does NOT independently close gap to $10/day.** Primary value is drawdown smoothing, not return enhancement — exactly aligning with LuxAlgo's "25% DD reduction" framing.

**Risk if applied wrong:**

- **Over-de-leveraging on routine micro-spikes** → starves high-edge setups during transient volatility blips. Mitigation: ATR-cap must use ATR(14) averaged, not raw 5-min realized range. Cap applies at proposal time, not intra-trade.
- **Decimal-token bias** → if decimal-perp ATR-%-of-price is structurally higher than majors, the cap blanket-de-leverages our highest-volume cohort. Mitigation: bucket diagnostic by price-tier (decimal vs whole-number) first; consider price-tier-conditional ATR cutoffs.
- **Stale ATR data** → using a 5-min candle from 10 min ago to size a new trade in a fast move is exactly the bug FXNX warns against. Mitigation: staleness check (ATR data ≤ 2 candles old).
- **Compounding with other filters** → rngpos + funding + OI + news + ATR could compress trade count from ~13/day to ~4/day. Mitigation: stage rollout one filter at a time, measure delta after each.

**Status:** Logged. Topic library entry added to `memory.md` "Volatility sizing" section. Item #1 rotates to bottom (revisit after `atr_pct_at_entry` logging produces ≥ 30 trades). Next fire takes item #2 (Market-regime classification — practical taxonomy beyond mixed/trending/ranging).

---

## RESEARCH-2026-05-12T20:55:00Z

**Question (queue item #1, on-rotation):** Are scheduled news-catalysts (Binance new-listings and token-unlocks) tradeable on the fade side, and what does the multi-thousand-event empirical literature say about timing windows, magnitude, and the *pre*-event vs *post*-event sweet spot? Specifically — given our scalp horizon (5-15 min holds), small wallet (~30 USDT), and locked $0.10 max-loss, can either event class produce a higher-conviction setup than our current rngpos-driven scans?

**Sources reviewed:**
- Keyrock, "From Locked to Liquidity: What 16,000+ Token Unlocks Teach Us" (study summary via crypto.news + beincrypto, primary URL 403-blocked) — https://crypto.news/token-unlocks-almost-always-negative-for-price-keyrocks-study-reveals/, https://beincrypto.com/keyrock-research-token-unlocks/, https://cryptoslate.com/90-of-token-unlocks-drive-prices-down-declines-begin-a-month-ahead/
- Yellow.com, "Token Unlocks Explained: How Vesting Schedules Impact Crypto Prices and Market Liquidity" — https://yellow.com/learn/token-unlocks-explained-how-vesting-schedules-impact-crypto-prices-and-market-liquidity
- BitPinas / CryptoNinjas & Storible joint study (Feb 2025, 389 tokens, 6 exchanges) — https://bitpinas.com/cryptocurrency/binance-token-listing-dump/
- AInvest, "Emerging Altcoin Opportunities on Binance Futures: Assessing Momentum and Liquidity in 2025" — https://www.ainvest.com/news/emerging-altcoin-opportunities-binance-futures-assessing-momentum-liquidity-2025-2509/
- Web Crypto Talk, "How The Crypto's Biggest Listing Signal Reversed" (referenced for the "ATH at listing" stat) — https://web.ourcryptotalk.com/blog/binance-effect-reversal-token-listing-performance

**Key finding (single strong idea):** **Both Binance listings and token unlocks are PRE-SCHEDULED, statistically-asymmetric, fade-favoring events with empirical data sets in the thousands.** The two together form a "calendar layer" that can produce setups with a known directional bias *before* any technical entry trigger fires — exactly the kind of high-conviction context our current rngpos-scan-only pipeline ignores. The critical timing window is **NOT** the event itself (which is noise-dominated) but the days surrounding it:

- **Unlocks (Keyrock, n=16,000+, cross-source-corroborated):** 90% of unlock events produce negative price pressure. Decline *begins 30 days before* the unlock, accelerates in the final week, and **strongest negative impact is concentrated 2 days BEFORE the unlock date** (Yellow.com). **Unlock day itself is muted; secondary impact emerges 3-4 days POST-unlock** as actual selling materialises. Stabilisation within ~14 days. Size impact is non-linear: large unlocks (5-10% of supply) drop 2.4× steeper than medium (1-5%). Team unlocks worst (-25% on average); ecosystem unlocks the only positive class (+1.18%).
- **New listings (BitPinas/CryptoNinjas study, n=389 across 6 CEXs, Feb 2025):** 98% of Binance-listed tokens eventually dump from listing price. Average initial pump = **+87%** on listing. Average post-listing decline = **−70% from listing peak**. **46% of tokens hit their all-time high AT listing and never surpass it.** Complementary AInvest 2025 commentary: the "Binance Effect" remains real but post-listing momentum is highly variable — concentration in first 24-48h pump then deterioration.

**Established (cited, with mapping to our locked policy):**

1. **Pre-unlock fade window: 2-7 days before the date.** Yellow.com directly states "best entry point for long positions occurs 14 days after significant unlocks once volatility settles, while optimal exit timing is 30 days before major unlocks." Implies the fade-short / no-long zone is **T-30d → T-2d**. For our 5-15 min scalp horizon, this becomes a *bias overlay*: a token entering its T-30d unlock window should NOT be a LONG candidate unless conviction is exceptional; SHORT proposals on the same token get a directional tailwind. Source: https://yellow.com/learn/token-unlocks-explained-how-vesting-schedules-impact-crypto-prices-and-market-liquidity

2. **Post-listing fade window: 24h-30d post-listing.** BitPinas study reports 98% Binance dump rate after the listing pump, and 46% of tokens print ATH at listing. Translation for our system: a newly-listed token in its first 24h is a LONG-bias trap (the 87% pump may already be gone by the time our scanner notices) and a SHORT-bias setup on retest of the listing-day high. Source: https://bitpinas.com/cryptocurrency/binance-token-listing-dump/

3. **Size and recipient matter.** Keyrock: large unlocks (>5% of float) drop 2.4× more than medium (1-5%); team/investor unlocks crash worst (-25%); ecosystem unlocks the only positive class. Source: https://cryptoslate.com/90-of-token-unlocks-drive-prices-down-declines-begin-a-month-ahead/. Implication: not all unlocks are tradeable — the filter must be unlock_size_pct_of_float ≥ 1% AND recipient ∈ {team, investor, private}.

4. **The "30 days ahead" anticipation effect IS the trade.** Keyrock/Yellow: institutional desks front-run by selling 30 days prior. Our 5-15 min scalp would not capture this directly, but the directional bias it creates means short setups in the T-30d → T-2d window have tailwind, longs have headwind. This is exactly the kind of cheap *context filter* that improves selection without raising risk.

**Speculative (label as such — needs our own validation):**

- **Whether the calendar-layer bias survives our 5-15 min scalp horizon specifically.** The literature is on daily/weekly horizons; our trades close before any unlock-related session even develops. Hypothesis: the *intraday* bias is still present (sellers leak liquidity throughout the day in anticipation), but magnitude is fractional. Needs own backtest from `data/trade-events.jsonl` cross-referenced against Tokenomist / DropsTab unlock calendars.
- **Whether decimal-priced small-caps follow the same unlock pattern as majors.** Most academic data is on top-100 tokens. Decimal-tier tokens may behave more extreme (thinner books + same supply shock) or more random (different holder mix). Treat magnitude as directional only.
- **Whether the listing-fade pattern holds for *futures listings* (vs spot listings).** Most cited data conflates the two. Binance USDT-M perp listings may follow a different cycle than spot listings since perps already have shorts available from day 1. Needs explicit separation in our own data.
- **Whether our 5-symbol scanner universe even *contains* tokens in their unlock window often enough to matter.** A pre-trade filter is only valuable if it fires on a meaningful % of proposals. Could be < 10% of trades affected.

**Mapping to our locked policy:**

Locked policy gates trades on confidence ≥ 0.75. A calendar-layer bias does NOT change confidence math directly — it changes the *prior* the strategy-agent should bring to a setup. Specifically:
- A LONG proposal on a token with T-7d to T-2d unlock window of ≥ 1% float: confidence ceiling −0.05 (so 0.78 nominal → 0.73 effective → BLOCKED by min-conf gate)
- A SHORT proposal on the same token: confidence floor +0.02 (so 0.73 nominal → 0.75 effective → GREEN)
- A newly-listed token in first 24h: hard NO-LONG (only SHORT on retest-of-high allowed)

This is a **context filter, not a risk parameter.** No change to margin (3.5 USDT), leverage ladder (2-15x), max-loss ($0.10), daily cap ($1.0), max-open (8), min-confidence (0.75). Filter only changes the *selection set*.

**Today's session match (2026-05-12 night, agency context):**

- 22 enhancement findings queued, 6+ hour pause, no fires; ONDO at 0.83 is "readiest setup for resume". We have NO calendar-layer data on ONDO. If ONDO has an unlock within 7 days, the LONG bias must be downgraded. If ONDO had a recent Binance listing within 30 days, similar bias. **Action: any LONG resume on ONDO should first cross-check Tokenomist + Binance announcements page before fire.**
- The 8 concurrent slots multiply the value of a calendar-layer filter: even a 10% reduction in selection set (skip 1-in-10 trades that face a calendar headwind) at our 13-trades/day rate = ~1.3 avoided losses per day. At an avg-loss of $0.18 that's ~$0.23/day saved — small but persistent and zero-risk.

**Action recommendations (NO risk-param changes; queue for user OK before any error-fix-agent spawn):**

1. **Diagnostic-first, lowest cost: add a daily `data/calendar-layer.json` snapshot** populated by a once-per-day cron that fetches:
   - Tokenomist or DropsTab API for upcoming unlocks (next 30 days, our top-100 watch universe), recording `symbol`, `unlock_date`, `unlock_pct_of_float`, `recipient_class`.
   - Binance announcements RSS / API for new-listing events (last 30 days), recording `symbol`, `listing_date`, `listing_type` (spot / perp / futures).
   This is **pure observation infrastructure** — no rule applied yet. Queue to error-fix-agent ONLY with user OK.

2. **After ≥ 30 trades with calendar data attached, scatterplot:** does a trade entered in T-7d unlock window for size ≥ 1% float underperform avg? If yes (and the empirical effect is at least 0.5σ), THEN propose the confidence-nudge filter above. Until then, **observe only**.

3. **Specific use today:** for the ONDO resume decision, manually check the next 14 days of ONDO unlocks (via tokenomist.ai) and recent Binance announcements before firing. One-time manual gate, no code change.

4. **NOT recommended:** auto-rejecting any trade in any unlock window without our own data. The literature is on top-100 spot tokens; our universe is alt-perps with different holder mix. Imposing a published filter blindly could over-cut our trade count and break the $2.5-5/day edge.

**Risk if applied wrong:**

- **Over-fitting published patterns to our small-cap perp universe:** if the literature-derived unlock bias doesn't actually carry to our specific symbols at our specific horizon, a confidence-nudge filter could block our highest-edge setups (e.g., a coincidentally-timed strong SHORT being green-lit, or a strong LONG being incorrectly blocked). Mitigation: 30-trade observation period FIRST, no auto-rule.
- **Stale calendar data:** Tokenomist / DropsTab APIs can lag actual on-chain events. A "no LONG within 7d of unlock" rule fed by stale data could be wrong about the window. Mitigation: require staleness check (data updated within 24h) before any rule fires.
- **Compounding with existing filters:** rngpos hard-reject + funding-sign filter + OI-delta filter + calendar-layer filter, applied together, could compress trade count from ~13/day to ~5/day. Mitigation: stage filter rollout one at a time, measure trade-count and edge after each.

**Profit-ratio implication (quantified hypothesis, label as needs-validation):**

If 10% of our daily trades face a documented calendar headwind and the filter avoids the bottom-quartile of those trades, expected lift = ~$0.20-0.40/day. Small but **structurally complementary** to rngpos / funding / OI work — different signal class (calendar vs. price/microstructure), so independence likely high. Does NOT independently close gap to $10/day, but at +0.30/day combined with other queued filters, lifts realistic ceiling from ~$2.5-5/day to ~$3-5.5/day on 30 USDT wallet.

**Escalation:** None — no exchange-level bug, no policy risk, no regulatory issue surfaced.

---

## RESEARCH-2026-05-12T20:15:00Z

**Question:** Carry-over safety pause UX — when an agency-wide pause is triggered (consecutive losses / daily-loss / safety event), should protective management of EXISTING positions (BE-trail, giveback-exit, loss-research EXIT) remain active while NEW fires stay blocked? What does industry practice say? (Triggered tonight: safety paused 6+ hours blocked BE-trails on FHE at r=+1.0 and BUSDT at r=+1.14, while USELESSUSDT swung $14 in 6h with no algorithmic intervention.)

**Sources reviewed:**
- Binance Futures support, "Reduce-Only mode" / MICA-compliance "switch to reduce only mode" — surfaced via FIA-derived search; confirms an exchange itself ships this exact two-mode pattern: "Some products will switch to 'reduce only' mode. This means you can only close existing positions; no new positions can be opened." — https://www.binance.com/en/support/faq/what-is-a-trailing-stop-order-360042299292 (Binance trailing-stop docs context); pattern described in cross-source coverage at https://blog.bitunix.com/en/reduce-only-order-in-crypto-trading/ and https://www.bybit.com/en/help-center/article/Reduce-Only-Order (per-order semantics — confirms reduceOnly is well-defined primitive used to build the mode)
- FIA "Best Practices for Automated Trading Risk Controls and System Safeguards" (Futures Industry Association, 2024) — https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf
- NYIF, "Trading System Kill Switch: Panacea or Pandora's Box?" — https://www.nyif.com/articles/trading-system-kill-switch-panacea-or-pandoras-box (quote: "Market participants and regulators have debated the need for multi-level kill switches, whereby an exchange or ATS would notify firms by phone calls or email before cutting off their order flow.")
- LuxAlgo, "Risk Management Strategies for Algo Trading" — https://www.luxalgo.com/blog/risk-management-strategies-for-algo-trading/ ("Stop-loss rules automate exits to minimize losses, while emergency controls employ kill switches and circuit breakers for major disruptions.")
- Bookmap, "Trading Circuit Breakers and Halts: How They Protect Markets and What Traders Should Know" — https://bookmap.com/blog/trading-circuit-breakers-and-halts-how-they-protect-markets-and-what-traders-should-know (documents that stop-loss orders remain PENDING during halts; the halt does not cancel protective orders — only suspends matching)
- Binance Futures API error-code reference, "Futures Trading Quantitative Rules violated, only reduceOnly order is allowed" — https://developers.binance.com/docs/derivatives/usds-margined-futures/error-code (the exchange's risk system itself emits a "reduceOnly only" state, NOT a full halt, when its quantitative rules trip)

**Key idea (single strong finding):** The "block new orders but explicitly allow protective management/closing of existing positions" pattern is **established exchange-level and regulator-level practice**, not a workaround. Binance Futures' own risk system, when it trips its quantitative-rules limits, does NOT halt the account — it transitions the account into reduceOnly-only state, where new opening orders are rejected with code `-2022` but reduce-only orders (stop-loss adjustments, partial closes, full closes) continue to function normally. Cross-market circuit breakers behave identically: stop-loss orders remain pending during the halt (Bookmap). The binary "everything off" pause our agency currently implements is the LESS-disciplined design — it is the unstudied/undefended dimension that NYIF's "Pandora's Box" article warns is the trap of an unconfigured kill switch.

**Established (cited):**

1. **Binance Futures itself implements the two-mode pattern.** When the exchange-level "Futures Trading Quantitative Rules" or "Futures Trading Risk Control Rules of large position holding" trip, the account is told via error code: *"only reduceOnly order is allowed, please reduce the position."* New positions are blocked; existing-position management continues. Source: https://developers.binance.com/docs/derivatives/usds-margined-futures/error-code

2. **Cross-market circuit breakers preserve stop-loss orders during halts.** *"Stop-loss orders remain pending during the halt but cannot execute until trading resumes."* The halt suspends matching — it does not delete or block the protective layer. Source: https://bookmap.com/blog/trading-circuit-breakers-and-halts-how-they-protect-markets-and-what-traders-should-know

3. **NYIF "Panacea or Pandora's Box?":** *"Market participants and regulators have debated the need for multi-level kill switches, whereby an exchange or ATS would notify firms by phone calls or email before cutting off their order flow."* The article explicitly frames binary kill switches as risky and graded responses as the regulator-debated alternative. Source: https://www.nyif.com/articles/trading-system-kill-switch-panacea-or-pandoras-box

4. **LuxAlgo risk-management taxonomy distinguishes two separate primitives:** *"Stop-loss rules automate exits to minimize losses, while emergency controls employ kill switches and circuit breakers for major disruptions."* Stop-loss layer and kill-switch layer are described as parallel, not nested — the kill switch does NOT subsume stop-loss management. Source: https://www.luxalgo.com/blog/risk-management-strategies-for-algo-trading/

5. **Reduce-only is a well-defined per-order primitive across all major exchanges** (Bybit, Binance, Bitunix). The semantics are settled: *"strictly reduce your position size... will not be unintentionally executed as a new position."* This is the building block any graded pause mode would use. Sources: https://www.bybit.com/en/help-center/article/Reduce-Only-Order, https://blog.bitunix.com/en/reduce-only-order-in-crypto-trading/

**Speculative (label as such — no published source specific to our setup):**

- **No academic backtest** found that quantifies the expectancy cost of a binary-mode pause vs a graded reduce-only-only-during-pause mode on small-account scalping. The session-specific evidence (tonight: FHE r=+1.0 and BUSDT r=+1.14 unable to be BE-trailed, USELESSUSDT $14 swing untouched) is anecdotal — a strong signal but n=1.
- Whether our `loss-research-agent` EXIT_EARLY verdicts should also be exempt from the pause, or only the deterministic BE-trail rule, is a design question the literature does not directly answer.
- Whether allowing protective actions during a pause materially raises the probability of an operational mistake (e.g., agency tries to modify SL, mis-fires a wrong-direction order) — no published incident data. Mitigation: limit allowed actions to a strict whitelist (tighten-SL only, reduce-only close, BE-trail rule).

**Today's empirical match (2026-05-12 night):**

- Safety paused 6+ hours after consecutive-losses trip. During the pause:
  - FHE reached r=+1.0 (BE-trail threshold) but BE move was blocked. If FHE later retraces below entry, the gain is given back to the original SL — a textbook "rule existed, rule was disabled, money lost" outcome.
  - BUSDT reached r=+1.14 (would have qualified for +0.5R lock) — same blocked-trail story.
  - USELESSUSDT user-managed position swung $14 (−$8.64 → +$5.04 → −$1.39 → +$2.68) with zero algorithmic giveback intervention. (Note: user-managed positions are DO_NOT_TOUCH by policy, but the pause prevents even monitoring-alert escalation that the user could have manually acted on.)
- This is the cry-wolf failure mode's evil twin: cry-wolf = too many low-value alerts desensitize; safety-pause-too-broad = a real alert exists but the system muted the action layer that would have responded.

**Mapping to our locked policy:** NO risk-parameter change proposed. Margin 3.5 / leverage 2-15x / max-loss 0.10 / min-conf 0.75 / daily-cap 4.0 / max-open 8 ALL untouched. This is a **pause-scope refinement** — the pause boundary moves, the risk parameters do not.

**Proposed action (NO risk-param changes; user-decision queued + low-risk code work that can be queued to error-fix-agent):**

1. **Define `PAUSE_MODE` enum in `scripts/safety_state.py`:**
   - `PAUSE_NEW_FIRES_ONLY` (NEW DEFAULT) — block strategy-agent / orchestrator from firing new trades; ALLOW watcher BE-trail, giveback-exit, loss-research EXIT_EARLY (once `run_close_position.py` exists), and any reduce-only adjustment that TIGHTENS protection (never widens).
   - `PAUSE_FULL_HALT` (current behavior; retained for emergency-shutdown skill explicit invocation).
   - `PAUSE_REDUCE_ONLY_ALL` (most restrictive non-emergency state — only reduce-only exits allowed, no SL tightening either; reserved for "we don't trust our own state" scenarios like reconciler-disagreement events).
2. **Whitelist of allowed actions in `PAUSE_NEW_FIRES_ONLY` mode** (must be code-enforced, not policy-document-only):
   - BE-trail SL move when r_curr ≥ 0.9R (TIGHTEN only)
   - Trail-to-lock SL moves at r_curr ≥ 1.5R / 2.0R / 2.5R (TIGHTEN only)
   - Giveback-protection reduce-only MARKET close
   - Loss-research EXIT_EARLY reduce-only close
   - Watcher status updates / journal writes
3. **Explicitly REJECTED during `PAUSE_NEW_FIRES_ONLY`:**
   - Any new entry order (`reduceOnly=false`)
   - Any SL widen
   - Any TP move beyond current (debatable — keep tight for safety)
   - Any leverage / margin-mode change
4. **`/status` skill must report current `PAUSE_MODE`** and the active allow-list so the user knows at a glance what the pause does and does not cover.
5. **Default for the consecutive-losses-3 trip and daily-loss trip should be `PAUSE_NEW_FIRES_ONLY`**, NOT full halt. The trip means "the agency's selection is bad right now"; it does NOT mean "the agency's exit math is broken." Selection logic and exit logic are independent code paths and should be paused independently. Full-halt is reserved for: reconciler-disagreement, watcher false-claim detection, API-key compromise suspicion, user manual `emergency-shutdown`.

**Risk if applied wrong:**

- **Over-permissioning the allow-list** → an action that "tightens SL" but is computed from stale data could still close a position at the wrong price. Mitigation: the price-validation guard already added in ERROR-20260511-4 is a hard prerequisite; this enhancement must be gated on its presence.
- **Under-permissioning** (e.g., loss-research EXIT_EARLY left blocked) → cry-wolf problem re-emerges from the other side. Mitigation: include all four "automated protective" rules in the allow-list, not a subset.
- **User confusion about pause states** → graded modes are harder to reason about than binary ones. Mitigation: `/status` MUST surface the current mode + the allow-list in plain English, and the mode must change ONLY at explicit boundaries (rule trip, manual override).
- **Order of operations during pause transition** — if a fresh tighten-SL fires the instant a daily-loss trip happens, it could race with the trip itself. Mitigation: pause-transition handler MUST drain any in-flight orders before flipping mode.

**Profit-ratio implication:**

Direct: tonight alone, if BE-trails on FHE (r=+1.0) and BUSDT (r=+1.14) had been allowed during the pause, two trades that may give back to original SL would have locked at breakeven or +0.5R. Conservative estimate: +$0.50 to +$1.20 NOT lost per session in which a pause spans an active runner. The agency triggered pauses ~2-3 times in the past week per session.md notes. Expected lift: +$0.5–1.5/week from pure giveback-prevention.

Indirect (much bigger): the **structural fix unblocks the entire R-trail enhancement queue.** Enhancement-agent's queued "R-trail not coded" finding becomes deployable; loss-research EXIT_EARLY becomes a first-class action once `run_close_position.py` ships. The pause-scope fix is a **prerequisite** for ~3 of the 19 queued enhancement findings to actually fire in production.

**Status: documented + queued for error-fix-agent spawn (low-risk: pure pause-scope refactor, gated on price-validation guard already in place, no risk-parameter change).** Recommend orchestrator spawn `error-fix-agent` to implement the `PAUSE_MODE` enum + whitelist after user OK. Implementation cost: ~150-200 LOC in `scripts/safety_state.py` + 3-4 watcher call-site updates + 1 `/status` skill update + tests.

---

## RESEARCH-2026-05-11T16:25:00Z

**Question:** Decimal-priced token edge — what makes 0.0XXX tokens trade differently than higher-priced assets, and what is the documented entry-zone discipline for these instruments? (Triggered by today's empirical pattern: two losers BILL and UB were rngpos ≥ 90% chase entries on decimal tokens.)

**Sources reviewed:**
- Alpha Architect / Interactive Brokers "Penny Stock Anomaly" research summary (search-snippet only; 403-blocked direct fetch) — https://alphaarchitect.com/low-priced-stocks/ and mirror https://www.interactivebrokers.com/campus/ibkr-quant-news/explaining-the-performance-of-low-priced-stocks-the-penny-stock-anomaly/
- Databento Microstructure Guide, "What is the Sub-Penny Rule?" — https://databento.com/microstructure/sub-penny-rule
- Saxo Bank, "Penny stocks explained" (execution-risk + wide-spread context) — https://www.home.saxo/learn/guides/equities/penny-stocks-explained-what-they-are-and-why-you-should-care
- Britannica Money, "What Are Penny Stocks?" — https://www.britannica.com/money/penny-stock-trading
- Tradeciety, "The Order Clustering Effect Around Round Numbers" — https://tradeciety.com/the-order-clustering-effect-around-round-numbers
- ScienceDirect / Finance Research Letters (Mbanga 2022), "Evidence for round number effects in cryptocurrencies prices" — https://www.sciencedirect.com/science/article/pii/S1544612322001179
- Coinpedia, "Price Action Mastery: Round Numbers and Their Crypto Trading Impact" — https://coinpedia.org/traders/price-action-mastery-round-numbers-and-their-crypto-trading-impact/
- Binance Square, "Updates Tick Size for Multiple USDⓈ-M Perpetual Futures Contracts" — https://www.binance.com/en/square/post/15637513224946
- Binance Support, "Updates on Tick Size for Multiple USDⓈ-M Perpetual Futures Contracts (2024-09-20)" — https://www.binance.com/en/support/announcement/updates-on-tick-size-for-multiple-usd%E2%93%A2-m-perpetual-futures-contracts-2024-09-20-fa192e78242d4d96be9562ab7d76a10a

**Key idea (single strong finding): Decimal-priced tokens carry a documented "penny-stock anomaly" risk profile — their per-tick percentage move is 5–10× larger than majors, their relative spreads are wide, and they exhibit STRONG round-number clustering. Combined with rngpos ≥ 90% entries, this is statistically the worst possible chase: you are buying inside a high-noise band where the next-tick adverse move is large in % terms AND you are buying directly into a documented sell-side resistance cluster. Today's BILL (−0.45) and UB (−0.30) losses are textbook examples.**

**Established (cited):**

1. **Volatility is structurally higher on low-priced instruments.** Alpha Architect / IBKR (search-snippet): low-priced stock universe shows standard deviation **29% vs 19%** for higher-priced peers — a **~53% higher SD** — and a Sharpe ratio of **−2.06 vs +0.61**. The conclusion: the lottery-ticket distribution that draws traders also delivers asymmetric drawdown. Crypto USDT-M decimal tokens (e.g. BILL ~0.00X, UB ~0.0X, NAORIS, SAGA, SKYAI tier) share the same micro-cap profile.

2. **Tick size as % of price is the hidden lever.** Databento (sub-penny-rule page; regulatory context for U.S. equities, principle is universal): minimum-tick discreteness has outsized effect on low-priced instruments because each tick is a large % of price. Binance's own 2024-09-20 announcement explicitly reduced tick sizes on multiple USDⓈ-M perps "to improve liquidity, allow tighter spreads and finer price discovery." The asymmetric reality: on a 0.0040 token, even after tighter ticks, a 1-tick move can be 0.25–1.0% — orders of magnitude noisier than BTC where 1 tick is < 0.001%.

3. **Round-number clustering is empirically confirmed in crypto.** Mbanga (2022, Finance Research Letters, ScienceDirect): "Evidence for round number effects in cryptocurrencies prices" — clustering present for ETH, XRP, LTC; **stronger at high-frequency timeframes** (1m–15m, where scalps live). Tradeciety: stop-loss orders for longs cluster BELOW round numbers; take-profit orders for longs cluster BELOW round numbers — meaning the top of an intraday range on a decimal token is mechanically a sell-pressure cluster, not a continuation point.

4. **Wide relative spreads on micro-caps eat scalp edge faster.** Saxo + Britannica: execution risk is dominated by wide bid–offer spreads on penny names. For a 0.50 USDT max-loss budget at 5–15× leverage on a decimal token, a 2-tick adverse slip on entry can consume 10–20% of the loss budget before the position even forms — meaningfully smaller for majors.

**Speculative (label):**

- Whether Binance Futures' more aggressive tick-size cuts on low-priced perps have measurably tightened or widened our realized slippage vs 6 months ago — no public study found; would require our own pre/post analysis from `data/trade-events.jsonl`.
- Whether decimal-token range-top sell clusters are more or less pronounced than for major-priced perps in our specific 5–30 min scalp window — no peer-reviewed crypto-futures source isolates this; the Mbanga (2022) clustering finding is generic.

**Profit-ratio implication (quantified):**

- Two of today's losses were rngpos ≥ 90% chases on decimal tokens — combined −0.75 USDT = roughly **47% of today's gross +1.6 net erosion**. If a rngpos ≥ 85% hard-reject were in force, today's net would have been ~+2.35 USDT instead of +1.6 (a **+47% lift**, no risk-param change required).
- On a 30 USDT wallet at locked policy, an empirical −0.45 + −0.30 = −0.75 loss-cluster avoided per ~13-trade day moves expectancy from +0.39R to roughly +0.54R (still below the "rare > 0.5R" threshold noted on luxalgo.com, but a material improvement that does not touch margin/leverage/max-loss).
- **The enhancement does not require raising risk** — it is a quality-gate tightening (entry zone discipline). Fully consistent with locked policy.

**Mapping to our locked policy:**

- No margin / leverage / max-loss / daily-cap / min-confidence change required.
- This is an **entry-quality filter**, which the enhancement agent has already proposed as a code-level rngpos hard-reject. Today's data + the cited microstructure literature support that proposal.
- Implementation suggestion (NOT auto-applied): treat rngpos ≥ 85% as hard-reject on decimal-priced symbols (price < 1.0 USDT), and rngpos ≥ 90% as hard-reject on all symbols. This pairs the documented penny-stock-anomaly volatility profile with the round-number clustering finding — both cited.

**Risk if applied wrong:**

- Hard-rejecting all high-rngpos entries could miss legitimate breakout continuations on strong-trend days (Tradeciety: round-numbers act as resistance OR launchpads depending on context). Mitigation: pair the rngpos filter with a trend-confirmation overlay (e.g. EMA-alignment + volume expansion) rather than a blanket rejection. This is a refinement, not a blocker.
- The penny-stock-anomaly SD/Sharpe numbers come from equities, not crypto perps. Direction is the same (low price → high noise) but magnitude on Binance Futures may differ. Treat the 53%-higher-SD figure as directional, not literal.

**Proposed action:** Hold for user. The code-level rngpos hard-reject already proposed by the enhancement agent is supported by today's empirical pattern + cited microstructure literature. The added refinement worth queueing for user OK: tier the rngpos threshold by price (≥ 0.85 for decimal-priced < 1.0 USDT; ≥ 0.90 for major-priced ≥ 1.0). No risk-parameter change required.

**Status:** documented; user-decision queued.

---

## RESEARCH-2026-05-11T15:53:34Z

**Question:** What does published literature + credible trader practice say about optimal MFE-pullback exit thresholds for HIGH-LEVERAGE SCALP trades (2-15x) on small-account crypto USDT-M Futures, 5-30 min duration? Specifically: (a) optimal pullback-from-MFE %; (b) does it scale with MFE magnitude; (c) time-based vs MFE-pullback; (d) Monte-Carlo / backtest comparisons of fixed-R-trail vs MFE-pullback vs hard-cap.

**Sources reviewed:**
- John Sweeney, *Maximum Adverse Excursion: Analyzing Price Fluctuations for Trading Management* (Wiley, 1996) — canonical reference, summary via https://dokumen.pub/maximum-adverse-excursion.html and https://journalplus.co/learn/glossary/mae/
- Dobrovolsky, *Setting Stops And Taking Profits With Maximum Excursion*, Technical Analysis of STOCKS & COMMODITIES, Aug 2002 — http://traders.com/documentation/feedbk_docs/2002/08/Abstracts_new/Dobrovolsky/dobrovolsly.html
- TradingMetrics docs on MFE / Exit Efficiency — https://docs.tradingmetrics.com/en/technical-analysis/trading-metrics/trade-specific-metrics/max-favorable-excursion (cites Kaufman *Trading Systems and Methods* 6e, 2020 + Sweeney 1996)
- LuxAlgo "5 ATR Stop-Loss Strategies" — https://www.luxalgo.com/blog/5-atr-stop-loss-strategies-for-risk-control/
- Chandelier Exit (Le Beau, in Elder) — https://www.quantifiedstrategies.com/chandelier-exit-strategy/ and https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/chandelier-exit

**Key idea (single strong finding): MFE-pullback thresholds should be DATA-DERIVED from one's own trade scatterplot, not set by industry rule-of-thumb. We have the data already and are not using it.**

Established (Sweeney 1996 + Dobrovolsky 2002, cited by Kaufman 2020): the canonical methodology is to scatterplot every trade's final PnL against its MFE peak, then locate the giveback threshold where the empirical probability of continued favorable excursion drops below the marginal-utility-of-waiting. Dobrovolsky's Figure 1 caption (from the public abstract): *"By adjusting profit-taking cutoff levels, you can end up with a system that results in better profitability."* The point is that thresholds should be EMPIRICALLY tuned per system, not borrowed.

Industry common-defaults found in the search (NOT validated for our system):
- Generic "exit on 50% giveback from MFE peak" appears widely (TradeWink, JournalPlus) — but **this is a swing-trade heuristic**.
- Scalp setups are noted to legitimately capture 50-65% of MFE (TradeWink summary in search), implying tighter giveback (i.e. 35-50% give-back tolerance) is normal for short-duration trades.
- Chandelier Exit (Le Beau) — ATR-multiple from highest-high. Standard 3× ATR (22-period) for trending; 1.5-2× for scalps (Lux Algo, ATR-Trailing variants). This is **fundamentally different from a fixed-USDT pullback**: it self-scales with volatility.
- LuxAlgo lists 5 ATR strategies. None cite backtest data, none scale by MFE magnitude — that pattern is uncommon in published material.

Time-based exits for scalps: the search returned **no peer-reviewed or named-trader study with backtested data** on "exit if MFE not exceeded for N minutes." It is a common discretionary practice (mentioned in coinbureau guides, fxopen 1-min scalping articles) but not a documented optimum. Label: **speculative — needs our own backtest before adoption.**

Backtest comparisons of fixed-R-trail vs MFE-pullback vs hard-cap: **no Monte-Carlo paper surfaced** on this specific three-way for small-account crypto futures. The Sweeney/Kaufman/Dobrovolsky chain is the closest established framework; everything beyond is single-author and uncited.

**Mapping to our locked Rule B (MFE-pullback tiers):**

Our current tiers are: MFE ≥ 1.0 USDT → exit on 0.25 USDT giveback (25% absolute); MFE ≥ 0.50 → exit on 0.15 (30%); MFE ≥ 0.30 → exit if uPnL ≤ MFE × 0.20 (80% giveback). Today's evidence:
- 4-5 fires today captured ~+1.07 USDT = 44% of day's net.
- Avg-win-after-rule-fire = +0.34 USDT vs system-wide avg-win = +0.567 → the rule fires on **smaller wins than typical**. It's preventing tail give-back but at the cost of cutting some trades short.
- The 80%-giveback tier (small-MFE) is loose by published-scalp standards. A scalper capturing only 20% of MFE is in the bottom decile of exit-efficiency (TradeWink defines 50-65% as the scalp norm).

**Profit-ratio implication:** none of the literature suggests we should *raise* USDT thresholds — that would risk more giveback. What the literature DOES suggest, with the strongest evidence base (Sweeney/Dobrovolsky/Kaufman chain), is that we should:
1. Log MFE-at-exit + final-PnL for every closed trade (we already do — `trade-events.jsonl` + watcher state).
2. Plot the scatterplot weekly once we have ≥ 30 closed trades.
3. Let our OWN data tell us where the optimal giveback knee is, rather than reusing the current hand-tuned tiers.

**Proposed action (NOT a risk-parameter change, NOT auto-executed):**

Add a **non-risk diagnostic**: `scripts/analyze_mfe_exit_efficiency.py` that reads `data/trade-events.jsonl` + `memory/trade-journal.md`, computes per-trade `exit_efficiency = realized_pnl / max_favorable_pnl`, and outputs:
- Histogram of capture ratios bucketed by MFE-magnitude tier (matching our 0.30/0.50/1.0 USDT tiers).
- For each tier: median capture %, count of trades that gave back to (a) breakeven, (b) loss, (c) full hard-cap, (d) MFE-pullback rule trigger.
- A *suggested* giveback threshold per tier where empirical hazard-rate-of-new-high drops below 30%.

This is **diagnostic-only**. Output is a report. **No automated change to Rule B thresholds.** User decides whether to act on the histogram. This complies with the agent constraint: "exit-rule THRESHOLD refinements ARE risk-touching → propose with data, QUEUE for user OK, do NOT auto-execute."

Speculative refinement candidate (label: SPECULATIVE, needs ≥ 30-trade scatterplot before user approval):
- Current 80% giveback at MFE ≥ 0.30 tier may be loose. If our scatterplot shows that trades reaching 0.30 USDT MFE rarely (< 30% of the time) push to ≥ 0.45 USDT MFE, then tightening to 60-65% giveback (exit at uPnL ≤ 0.10-0.12 instead of 0.06) would lift capture-ratio without meaningfully hurting upside. **This is a HYPOTHESIS, not a recommendation, until our scatterplot confirms it.**

**Status:** documented. Proposed action (build diagnostic script) is non-risk and can be queued to error-fix-agent only with explicit user approval per agent constraints. Any actual threshold refinement is queued for user.

---

## RESEARCH-2026-05-11T15:43:14Z

**Question:** For path to ~$10/day realized PnL on a 30 USDT wallet under our locked policy, which of (a) higher avg-win, (b) higher win-rate, (c) smaller avg-loss, (d) faster slot recycling, (e) better trade selection has the strongest published evidence base + cleanest fit?

**Sources reviewed:**
- Van Tharp "Tharp Think Trading Concepts" — https://vantharpinstitute.com/tharp-think-trading-concepts/ (fetched via search snippet; direct fetch 403'd)
- P&L Ledger "Expectancy & R-multiples: the plain-English guide" — https://www.pnlledger.com/expectancy-r-multiples-the-plain-english-guide/
- Wikipedia "Kelly criterion" — https://en.wikipedia.org/wiki/Kelly_criterion
- Hyrotrader "Most Profitable Trading Strategy: Data-Backed Guide" — https://www.hyrotrader.com/blog/most-profitable-trading-strategy/
- LuxAlgo "Win Rate and Risk/Reward: Connection Explained" — https://www.luxalgo.com/blog/win-rate-and-riskreward-connection-explained/

**Key idea (single strong finding): Expectancy-in-R is the only metric that ranks the five paths.**

Per Van Tharp (cited in pnlledger.com): `Expectancy in R = p × AvgWinR + (1 − p) × AvgLossR`. Our current numbers:
- Max planned loss = 0.50 USDT STRICT → 1R = 0.50 USDT
- Avg win realized = +0.567 USDT = **+1.134R**
- Avg loss realized = −0.177 USDT = **−0.354R**  (we're cutting losses well — at ~35% of full R)
- WR = 0.50
- Expectancy = 0.5(1.134) + 0.5(−0.354) = **+0.39R per trade ≈ +0.195 USDT/trade**
- At 13 trades/day → +2.53 USDT/day (matches today's +2.4 actual within noise)

Sensitivity: what gets us to $10/day at locked 0.50 max-loss?

| Path | Required change | Realistic? |
|---|---|---|
| (a) avg-win up | +1.134R → +5.4R win (≈ +2.7 USDT each) at same WR & count | UNREALISTIC on 5-15 min scalps |
| (b) WR up | 0.50 → ~0.85 WR at same R:W | UNREALISTIC — best discretionary edges plateau 55-65% |
| (c) avg-loss down | already at −0.35R (only 0.15R headroom left) | MARGINAL gain |
| (d) more trades | 13 → 51/day | VIOLATES discipline + per-cycle cap |
| (e) better selection | combo: WR 0.55 + avg-win 1.5R + avg-loss −0.30R → +0.69R/trade × 20 trades/day = +6.9 USDT | **PARTIALLY FEASIBLE** |

**Compounded answer:** No single path gets us to $10/day under locked policy. The literature (LuxAlgo, Hyrotrader) explicitly warns that single-variable optimization fails; pros optimize **expectancy-per-trade × frequency together**. To stay disciplined we must accept that ~$5-7/day is the engineering ceiling on 30 USDT until either (i) wallet grows (Kelly geometric compounding) or (ii) a verifiable new edge raises expectancy.

**Kelly cross-check (Wikipedia formula):** f* = p − q/b. With p=0.5, b = 0.567/0.177 = 3.20 → f* = 0.5 − 0.5/3.20 = **0.344 (34.4% full Kelly)**. Half-Kelly recommended for live trading with edge uncertainty = **17.2% per "bet."** We're currently deploying 93% of wallet across 8 concurrent positions (28/30 USDT margin). When correlated (which alt-futures slots are), this is closer to full-Kelly than half-Kelly. Established literature warning (Wikipedia): "betting an amount larger than the Kelly amount increases the risk of ruin." Caveat — Kelly assumes independent bets; concurrent same-direction alt-coin positions are NOT independent, so effective Kelly fraction is lower than the formula suggests.

**Profit-ratio implication:** $10/day on 30 USDT = 33%/day = mathematically requires either >full-Kelly aggression (forbidden, blow-up almost sure) OR an unverified high-edge strategy. With our verified +0.39R expectancy, sustainable target is **+2.5 to +5 USDT/day = 8-17%/day**, which is itself top-decile professional performance. The $10/day target is achievable only as the **monthly average compounds the wallet** — at +5 USDT/day net, wallet reaches 60 USDT in ~6 days, 120 USDT in ~12 days, and then +5/day becomes +10/day at same percentage edge.

**Proposed action:** DOCUMENT ONLY. No risk-parameter change proposed. Two non-risk suggestions for user to consider:
1. **Reframe daily target to "% of wallet, not absolute USDT"** — chasing absolute $10/day on a small wallet forces over-leverage. Set target at 10-15% of current wallet/day (= +3 to +4.5 USDT today, +6 to +9 USDT once wallet hits 60).
2. **Track expectancy-in-R daily in `data/risk-state.json`** so trend visible — speculative code refinement; would queue error-fix-agent only on user OK.

**Status:** documented

---

## RESEARCH-2026-05-11T16:55Z

**Question:** Funding-rate squeeze setups — at what negative-funding threshold does a small-cap altcoin perpetual become a high-probability long-mean-reversion candidate, and how does this map to our same-symbol re-entry losses today (BILL 3x, ALCH-reentry, UB, BLUAI)?

**Sources reviewed:**
- Yellow.com "How Funding Rates Predict Crypto's Most Violent Reversals" — https://yellow.com/learn/how-to-read-funding-rates-crypto-reversals (skewed to long-side; weak on negative-side numbers)
- Coinbase Learn "Understanding Funding Rates in Perpetual Futures" — https://www.coinbase.com/learn/perpetual-futures/understanding-funding-rates-in-perpetual-futures
- Flipster Blog "Mean Reversion in Crypto: How to Trade Oversold and Overbought Perps" — https://flipster.io/en/blog/mean-reversion-in-crypto-how-to-trade-oversold-and-overbought-perps
- Amberdata "Funding Rates: How They Impact Perpetual Swap Positions" — https://blog.amberdata.io/funding-rates-how-they-impact-perpetual-swap-positions
- BingX Learn "What Is Funding Rate Arbitrage in Crypto?" — https://bingx.com/en/learn/article/what-is-funding-rate-arbitrage-guide-for-futures-traders
- BitMEX 2025 Q3 Derivatives Report "Funding Rates Structure: Floor & Ceiling" — https://www.bitmex.com/blog/2025q3-derivatives-report

**Key idea (single strong finding): The ±0.05%/8h funding-rate threshold is the canonical "extreme" line in published material, but for small-cap altcoins the contrarian signal is unreliable WITHOUT a multi-indicator confirmation stack — and our same-symbol re-entry losses today are the textbook anti-pattern (continuation-chase into a one-sided book).**

Established (cited):

1. **Canonical extreme threshold: |funding| ≥ 0.05% per 8h funding interval = top/bottom 10th percentile** (search-consensus from CoinAPI / Yellow.com / BingX). March 2020 BTC bottom example: funding ran −0.05% to −0.15% per interval for multiple cycles → recovery rally (search-snippet, BTC-specific, not isolated altcoin).

2. **Multi-signal confirmation stack required (Flipster):** extreme funding ALONE is not a trade. Confirmed entries demand: (a) RSI > 70 short / < 30 long, (b) price outside Bollinger band, (c) doji/engulfing/volume-spike candle showing exhaustion, AND (d) funding extreme. Funding without the other three has high false-signal rate in continuing trends.

3. **Altcoin-specific caveat (BingX + Saxo penny-stock parallel cited earlier):** small-cap perps run more-extreme rates due to thinner books; same extreme funding number that means "stretched" on BTC may still be normal-tape on a decimal-priced alt. Direct translation of BTC thresholds to small caps is unsafe. Slippage on entry can eat the entire edge — "in thin markets the bid-ask spread alone can cost more than a single funding payment" (BingX).

4. **Direction of continuation vs reversal:** funding extremes signal *eventual* mean-reversion but timing is unbounded. BitMEX Q3-2025 report observes funding can stay pinned at floor/ceiling for extended periods during strong trends. Cited risk: "a trader who shorts purely because the rate is high can sustain significant losses before any reversal materializes" (Yellow.com). Symmetric for negative funding + long entry.

**Mapping to today's data:**

The user-flagged same-symbol re-entry pattern (BILL 3x, ALCH-reentry, UB SL after 1 min, BLUAI re-entry now −0.14R) shares a precise structural diagnosis with the funding-rate literature:

- All four are small-cap decimal-priced perps where funding likely sits at one extreme during the trend.
- Re-entry without checking funding direction = entering on the *paying side* of the funding flow (paying funding to the crowd we're joining).
- The strategy-agent today entered these with rngpos ≥ 85% and no funding-rate filter — exactly the high-tick-noise + paying-funding + chasing-trend stack the literature warns against.
- Counter-position (catching the reversal) requires the full Flipster confirmation stack — which we do not currently compute on re-entries.

**Speculative (label as such — no published crypto-futures backtest specific to our 5–15 min scalp horizon):**

- Whether funding-rate sign alone (regardless of magnitude) would have flagged today's BILL/UB/ALCH/BLUAI losses as bad re-entries — no published backtest available; needs our own analysis from `data/trade-events.jsonl` cross-joined with historical funding data.
- Whether a "funding-rate veto on third re-entry within 4h" would have prevented the BILL 3-attempt cluster specifically — speculative; same-symbol streak count is a non-funding proxy that already captures most of the signal.

**Profit-ratio implication:** If a "funding-direction check on re-entry" had blocked the 4 today (BILL ×3 + UB + ALCH-reentry + BLUAI), saved losses ≈ 4 × 0.30 = +1.20 USDT. Net day would lift from ~+2.4 to ~+3.6 USDT (+50%). This is the same magnitude as the rngpos hard-reject proposal — and likely partially overlaps with it (rngpos and funding both fire on chase-entries). Independent lift is probably +0.3 to +0.7 USDT/day.

**Action recommendations (NO risk-param changes; user-decision queued):**

1. **Diagnostic-only (queue to error-fix-agent ONLY with user OK):** add Binance funding-rate fetch to the strategy-agent's pre-trade context (already cheap via `/fapi/v1/premiumIndex`). Log funding sign + magnitude on every proposal in `data/trade-events.jsonl`. **No filter applied yet — pure observation.** After ≥ 30 trades, build the empirical scatter of (funding_sign × side × outcome) to see whether "entering on the paying side" empirically underperforms in our specific 5-15 min horizon.

2. **Speculative refinement (HYPOTHESIS, requires 30-trade empirical evidence before user approval):** on same-symbol re-entry within 4h, require funding-rate sign to FAVOR our direction (i.e. we want to be the receiving side, not paying). Negative funding + LONG re-entry = green; negative funding + SHORT re-entry within 4h = red flag. **Do not auto-apply.**

3. **Education (no action):** the user-locked rngpos hard-reject proposal (separate research thread) and this funding-direction check are complementary — both attack the same chase-entry failure mode from different angles. If only one is implemented, rngpos is the higher-confidence pick because it's confirmed by clustering literature (Mbanga 2022) plus today's strong empirical match; funding-direction needs our own backtest first.

**Risk if applied wrong:**

- Treating funding-extreme as standalone signal → counter-trend entries in strong continuations → exactly the "shorts pile in, get squeezed" outcome the literature describes from the opposite side.
- Blanket "no entry against funding direction" → blocks legitimate breakout trades against a fading funding bias → reduces trade count.
- Mitigation: funding rule fires ONLY on re-entry within short window (4h), not on first entry, and is paired with the Flipster confirmation stack before any contrarian use.

**Proposed action:** DOCUMENT ONLY for now. Diagnostic logging of funding-rate on every proposal is the only non-risk-touching step worth queueing — and only with explicit user OK.

**Status:** documented

---

## RESEARCH-2026-05-11T18:23Z

**Question:** Open-interest delta interpretation — what does each of the 4 quadrants (price-up/down × OI-up/down) actually signal, and how do we distinguish long capitulation from trend continuation? (Top of rotation queue. Today's HUSDT-2 re-entry WIN +0.44 vs UB/BILL re-entry LOSERS suggests OI direction at re-entry time may discriminate which re-entry succeeds.)

**Sources reviewed:**
- CryptoCred, "Comprehensive Guide to Crypto Futures Indicators" (Medium) — https://medium.com/@cryptocreddy/comprehensive-guide-to-crypto-futures-indicators-f88d7da0c1b5
- trdr.io official docs, "Open Interest / Open Interest Delta" — https://docs.trdr.io/key-features-and-indicators/sentiment-indicators/open-interest-open-interest-delta
- Hyblock Academy, "Open Interest" indicator page — https://academy.hyblockcapital.com/indicators/orderflow-and-open-interest/open-interest
- XT Exchange / Medium (Apr 2026), "Bitcoin Futures Market Microstructure: Liquidation Cascades, Funding Regimes, and Open Interest Signals" — https://medium.com/@XT_com/bitcoin-futures-market-microstructure-liquidation-cascades-funding-regimes-and-open-interest-978b107b4889
- Gate.com Crypto-Wiki (Jan 2026), "How do crypto derivatives market signals predict price movements" — https://www.gate.com/crypto-wiki/article/how-do-crypto-derivatives-market-signals-predict-price-movements-futures-open-interest-funding-rates-liquidation-data-long-short-ratio-and-options-explained-20260129

**Key idea (single strong finding): The 4-quadrant OI-delta map is the canonical filter for "is this move conviction or exhaustion?" — and it directly discriminates good re-entries from bad ones. Established consensus across all 4 cited sources:**

| Price | OI | Canonical signal | Re-entry implication |
| --- | --- | --- | --- |
| ↑ | ↑ | **Trend continuation** — new longs opening | LONG re-entry GREEN |
| ↑ | ↓ | **Short-cover rally / trend weakening** — existing shorts closing, no new buying | LONG re-entry RED (mean-reverts) |
| ↓ | ↑ | **Trend continuation down** — new shorts opening | SHORT re-entry GREEN |
| ↓ | ↓ | **Long capitulation / exhaustion** — longs closing, no new selling, reversal proximate | SHORT re-entry RED |

**Established (cited):**

1. **trdr.io official taxonomy** (exact quotes):
   - Price↑+OI↑: *"Indicates a strong trend as traders are actively opening new positions to capture the price move."*
   - Price↑+OI↓: *"Suggests a weakening trend with potential for no follow-through, as traders may be taking profits or closing positions."*
   - Price↓+OI↑: *"Signifies a strong downtrend, with new short positions opening during the price drop."*
   - Price↓+OI↓: *"Suggests a weak downtrend, and a potential reversal may be on the horizon."*

2. **CryptoCred caveat (critical):** *"For every buyer there is a seller / for every seller there is a buyer, so OI is always comprised of 50% longs and 50% shorts."* OI delta does NOT signal "more longs than shorts" — it signals **aggregate positioning change**. Combine with delta/CVD + funding to disambiguate which side is aggressive.

3. **Hyblock Academy — consolidation interpretation:** *"high OI during consolidation means more participants are taking positions and when price breakout occurs, we see increased volatility as one side has their stops triggered leading to a liquidity cascade."* Inverse: *"if OI remains flat or decreases during consolidation, then we may not expect major market volatility. Price may not be ready to breakout."*

4. **Hyblock — capitulation signal:** *"a sharp price movement + OI drop leads to a reversal … as trapped traders exit, there may not be enough interest or fuel to continue the trend."*

5. **XT Exchange — breakout integrity rule:** *"a breakout accompanied by rising OI is structurally sound, while a breakout on falling OI is a liquidity grab and will likely mean-revert."* This is the cleanest discriminator we have for chase-entry decisions.

**Speculative (label as such):**

- **No source provides a specific % OI-change threshold** ("≥5% over 15 min = significant"). All four sources use relative language ("sharp", "large", "high"). Empirical threshold must be calibrated from our own scatterplot.
- Whether Binance's `/fapi/v1/openInterest` 5-min delta is sufficient resolution for our 5–15 min scalp horizon, vs needing 1-min sampling — needs our own latency test.
- Whether decimal-priced perps follow the same 4-quadrant map cleanly, or whether their thin books make OI delta noisier than for majors — no source isolates the small-cap subgroup.

**Today's empirical match:**
- **HUSDT-2 re-entry WIN +0.44**: distinguishable from UB/BILL re-entry LOSERS if (and only if) HUSDT entered in a Price↑+OI↑ regime while UB/BILL entered in Price↑+OI↓ (short-cover rally fading). UNVERIFIED — we don't currently log OI delta at entry.
- **USELESSUSDT user 10x position +$1.43 unrealized**: memecoin Solana-ecosystem run — exactly the Price↑+OI↑ "fresh longs entering" profile.
- **SKYAI 80%-giveback exit**: post-exit price action is a textbook Price↑+OI↓ profit-take rally — confirms the giveback rule fires correctly.

**Profit-ratio implication:**

If we could filter today's BILL ×3 + UB + ALCH-reentry + BLUAI re-entry cluster (combined ≈ −1.2 USDT) by requiring **OI delta to confirm direction** at re-entry time, day lifts ~+2.4 → ~+3.6 USDT. Overlaps with rngpos hard-reject AND funding-direction filter from prior research — independent lift from OI-delta filter ALONE estimated +0.2 to +0.5 USDT/day. The three filters together attack the same chase-entry failure mode from three angles: (a) rngpos = price-location filter, (b) funding-sign = cost-of-carry filter, (c) OI-delta = conviction filter. They are correlated but not redundant.

**Mapping to our locked policy:** NO risk-parameter change. This is a pre-trade context enrichment (same category as funding-rate logging proposed in prior research).

**Proposed action (NO risk-param changes, user-decision queued):**

1. **Diagnostic-only first:** add Binance `/fapi/v1/openInterest` 5-min delta to strategy-agent's pre-trade context. Log OI delta sign + magnitude on every proposal. NO filter applied yet — observe ≥ 30 trades before any rule. Queue to error-fix-agent ONLY with explicit user OK.

2. **Speculative hypothesis (requires ≥ 30-trade evidence first, do NOT auto-apply):** on same-symbol re-entry within 4h, require OI-delta sign to confirm direction (LONG re-entry needs OI rising; SHORT re-entry needs OI rising while price falling). Negative OI delta on re-entry attempts → re-entry REJECTED.

3. **Hierarchy if only one filter ships:** prefer **rngpos** (strongest off-the-shelf evidence — Mbanga 2022 + today's match). OI-delta is third priority behind funding-sign because it requires extra API call per proposal and adds latency to the cycle.

**Risk if applied wrong:**

- Treating Price↑+OI↓ as a hard NO-LONG → misses legitimate squeeze-driven rallies that continue after short-cover-then-fresh-longs handoff. Mitigation: limit OI-delta filter to RE-ENTRY decisions only, not first entries.
- Sampling resolution too coarse (5-min snapshots) → OI delta lags actual flow → filter fires AFTER the move starts → adverse selection. Mitigation: confirm 1-min granularity available before any rule implementation.

**Status:** documented

---

## RESEARCH-2026-05-12T19:17:00Z

**Question:** Time-of-day session edge — is there a statistically documented intraday hour-of-day or session window in BTC/crypto futures that would tilt our 5–15 min scalps' expectancy, and does it survive sample-period robustness?

**Sources reviewed:**
- Quantpedia, "Are There Seasonal Intraday or Overnight Anomalies in Bitcoin?" — https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin/
- Quantpedia, "Overnight Seasonality in Bitcoin" (strategy page with backtest numbers) — https://quantpedia.com/strategies/intraday-seasonality-in-bitcoin
- Concretum Group, "Seasonality in Bitcoin Intraday Trend Trading" — https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/
- Quantpedia, "The Seasonality of Bitcoin" — https://quantpedia.com/the-seasonality-of-bitcoin/
- arXiv 2402.11930, "Stylized Facts of High-Frequency Bitcoin Time Series" — https://arxiv.org/html/2402.11930v2

**Key idea (single strong finding): Two independent quant studies converge on a positive-drift window for BTC: (a) Quantpedia's hourly analysis on Gemini data 2015-10-09 to 2022-02-03 finds 22:00–00:00 UTC as the most statistically significant positive-return window (5% level), yielding a stand-alone long-only strategy of 33% annualized return at Sharpe 1.58; (b) Concretum Group's 2018–2025 intraday trend-following backtest documents a "Monday Asia Open Effect" — Sunday ~23:00 UTC (Tokyo open) to Monday ~23:00 UTC delivers strongly positive returns and the high-frequency trend portfolio carries gross Sharpe ~1.6 vs ~0.8 for volatility-targeted long-only. Both effects coincide with a 22:00–04:00 UTC window where ALL major TradFi exchanges (NYSE, London, Tokyo, HK) are simultaneously closed — i.e. when retail/algo crypto-native flow dominates. The inverse: 03:00–04:00 UTC has the worst (though statistically insignificant) returns; Sunday US morning is "choppier and mean-reverting" (Concretum).**

**Established (cited):**

1. **22:00–23:00 UTC positive-return concentration.** Quantpedia (Gemini hourly data, 2015–2022): "the most sizeable and significant returns relate to the 22:00 and 23:00 hours (UTC +0)... statistically significant on the 5% level." Strategy: long at 22:00 UTC, exit 00:00 UTC → 33% ann. return, Sharpe 1.58, max DD −34%, annualized vol 20.93%. Source: https://quantpedia.com/strategies/intraday-seasonality-in-bitcoin

2. **"Monday Asia Open Effect" (Concretum, 2018–2025).** Trend-following portfolio "delivers strongly positive returns starting on Sunday at around 7:00 PM New York time (≈ 23:00–00:00 UTC), with performance remaining elevated for roughly the next 24 hours into Monday." Gross Sharpe ≈ 1.6 vs vol-targeted long-only ≈ 0.8. Effect strengthened post mid-2020, aligned with institutional participation. Source: https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/

3. **Worst-window (Quantpedia same study):** 03:00–04:00 UTC has the worst sample returns but is "statistically insignificant" — directional caution flag, not a hard sell signal. Source: https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin/

4. **Turn-of-the-candle micro-effect (arXiv 2402.11930).** Positive returns of +0.58 bps per minute concentrated at minutes 0/15/30/45 of each trading hour; other minutes average negative. Detected from mid-2020 onward; attributed to algorithmic execution. Source: https://arxiv.org/html/2402.11930v2

5. **Asia session general character (industry consensus).** Lower volume, narrower ranges, more sideways action during major US/EU off-hours — except for the documented late-evening UTC window above. Source: https://medium.com/@mzain10/why-asian-new-york-and-london-times-matter-in-crypto-trading-c00ad9dfe8e9

**Speculative (label as such — must be validated by our own backtest before any action):**

- All Quantpedia/Concretum results are on BTC/ETH majors. **Whether the same 22:00–00:00 UTC tilt extends to small-cap decimal-priced altcoins** (BILL, UB, NAORIS, SAGA, SKYAI tier) is NOT directly studied. Altcoin flow is largely a leveraged-beta of BTC during these hours — directional tilt likely carries, magnitudes may differ.
- Whether our own trade-events.jsonl shows the same hour-of-day skew on our actual fills (entry-time vs realized-PnL scatterplot) — UNVERIFIED. We do not currently bucket realized PnL by entry hour.
- Whether the 22:00–00:00 UTC long-bias signal materially helps SHORT scalps in the same window (i.e. asymmetric — only helps longs, not shorts). Quantpedia data is long-only; no documented short-side reversal.
- Whether Concretum's "Monday Asia Open" trend-portfolio Sharpe 1.6 survives transaction costs and slippage on Binance USDT-M perps at our 5–15 min horizon. Their portfolio is higher-frequency trend on majors; ours is decimal-altcoin scalp.

**Today's empirical match (2026-05-12):**

- Cannot verify against our own data yet — `data/trade-events.jsonl` is not currently bucketed by hour-of-day. The USELESSUSDT 10x runner (+$5+ unrealized) and today's stronger winners would be valuable scatterplot points to confirm whether our fills cluster in or out of the 22:00–00:00 UTC band.
- Cross-check against rejected-trades.md and our daily expectancy +0.39R: if a meaningful share of our wins land in the 22:00–00:00 UTC window, that strengthens the case; if wins are evenly distributed across hours, our edge may be regime-driven (small-cap rotation) rather than session-driven and the BTC literature transfers only weakly.

**Mapping to our locked policy:** NO risk-parameter change proposed. This is a pre-trade context enrichment + posterior-analysis diagnostic. Margin 3.5 / leverage 2-15x / max-loss 0.50 / min-confidence 0.75 / daily-cap 4.0 / max-open 8 all untouched.

**Proposed action (NO risk-param changes, user-decision queued):**

1. **Diagnostic script `scripts/analyze_entry_hour_pnl.py`** (queue to error-fix-agent ONLY with explicit user OK) that reads `data/trade-events.jsonl` + closed-trade journal, buckets realized PnL and win-rate by entry hour-of-day UTC + day-of-week, outputs a heatmap-style table. Pure observation, no rule change. Needed before any session-edge filter can be proposed for our specific decimal-altcoin scalp universe.

2. **Speculative hypothesis (requires ≥ 50 closed trades bucketed by hour first):** if our scatterplot confirms the BTC pattern carries to alts, add a confidence bonus of +0.02 (NOT a hard filter) for LONG proposals firing in 22:00–00:00 UTC and a +0.02 penalty for LONG proposals in 03:00–05:00 UTC. Stays inside the 0.75 min-confidence gate — does NOT lower it, only nudges proposals near the gate. Do NOT auto-apply without explicit user OK after backtest evidence.

3. **Lowest-effort first step:** add `entry_hour_utc` and `entry_session` (Asia / EU / NY-overlap / Late-NY-Off) fields to trade-journal records going forward, so the scatterplot becomes possible without re-parsing timestamps. Non-risk-touching, deterministic — still queue for user OK per agent constraints.

**Profit-ratio implication (cautious, BTC-derived):**

If our decimal-altcoin scalp universe inherits even half the BTC late-UTC tilt, concentrating LONG entries in the 22:00–00:00 UTC band could lift win rate ~3–5 pp during that window. With our +0.39R expectancy and ~13 trades/day, a 5-pp WR bump on ~30% of trades that fall in that window adds roughly +0.15–0.30 USDT/day. Material but small; **does NOT independently close the gap to $10/day**. Complementary to rngpos / funding-sign / OI-delta filters from prior research — all four attack expectancy from independent axes.

**Risk if applied wrong:**

- Over-fitting to a BTC-major-derived pattern that does not actually carry to small-cap decimal alts → confidence-bonus fires on losing setups → degrades selection. Mitigation: backtest first, deploy only as a CONFIDENCE NUDGE not a hard filter, and only on LONGs (literature is asymmetric).
- Sample-period bias: Quantpedia's 22:00–00:00 UTC window strengthened post-2020 with algo flow; could weaken if institutional flow rotates. Mitigation: re-validate on rolling 90-day window if implemented.
- Conflating session-edge with regime-edge: if 22:00–00:00 UTC tilt is actually driven by US-late-evening algo concentration (per arXiv 2402.11930 turn-of-candle effect), the signal is fragile and dependent on a single market microstructure regime persisting.

**Status:** documented

---

## RESEARCH-2026-05-12T00:00:00Z

**Question:** At our newly tightened max-loss of $0.10 per trade (1R = $0.10, was $0.50), what is the fee-adjusted break-even win rate across our 2x–15x leverage ladder, and at which tier do Binance taker fees become material relative to 1R?

**Sources reviewed:**
- Binance Official, "USDⓈ-M Futures Trading Fee Rate" — https://www.binance.com/en/fee/futureFee
- Binance Blog, "Maker vs. Taker Costs – And How To Minimize Them" — https://www.binance.com/en/blog/futures/421499824684902239 (regular taker 0.045%, regular maker 0.018%; worked $40k BTC example shows round-trip taker = $40.25 vs maker = $16.10)
- Trader's Second Brain, "Trading Expectancy Formula: The Number That Shows Edge" — https://traderssecondbrain.com/guides/expectancy-formula ("If your expectancy per trade is less than your average cost per trade (commissions + spread + slippage), you do not have an edge"; Example 3 demonstrates a +$2.50 raw expectancy turning NEGATIVE after fees in forex)
- Enlightened Stock Trading, "Trading Expectancy Calculator" — https://enlightenedstocktrading.com/trading-expectancy-calculator/ ("When you trade often with a system with a small positive expectancy, trading costs can quickly eat away your profits or even turn your expectancy negative")
- Babypips Forexpedia, "Expectancy" — https://www.babypips.com/forexpedia/expectancy (canonical BE-WR derivation: setting E=0 in `E = p·W − (1−p)·L`)

**Key idea (single strong finding): Tightening max-loss from $0.50 to $0.10 multiplies the fee-burden-per-1R by 5x, because round-trip fees scale with NOTIONAL while 1R scales with our chosen risk dollars. At 15x leverage on $3.5 margin ($52.5 notional), a round-trip all-taker fee of $0.047 now consumes 47% of 1R BEFORE any price move — versus only 9.5% under yesterday's $0.50 cap. This silently raises the break-even win rate at each leverage tier and erodes high-leverage edge fastest.**

**Established (cited):**

1. **Binance regular-user fee schedule (https://www.binance.com/en/fee/futureFee + https://www.binance.com/en/blog/futures/421499824684902239):** maker 0.018%, taker 0.045% on USDⓈ-M perps. BNB-fee discount knocks 10% off (taker ≈ 0.0405%). Round-trip all-taker = 0.09% of notional; all-maker = 0.036%; mixed (limit entry + market exit) = 0.063%.

2. **Fee burden formula:** `fee_as_fraction_of_1R = (round_trip_fee_pct × notional) / max_loss_usdt`. With max-loss now fixed at $0.10 and margin fixed at $3.5, notional = $3.5 × leverage, so `fee_burden = 0.0009 × 3.5 × L / 0.10 = 0.0315 × L` for all-taker. **Burden scales linearly with leverage.**

3. **Tabulated fee burden under tightened policy (2026-05-12):**

| Leverage | Notional | All-taker round-trip fee | % of 1R ($0.10) | Was % of 1R when 1R=$0.50 |
| --- | --- | --- | --- | --- |
| 2x | $7.0 | $0.0063 | **6.3%** | 1.3% |
| 3x | $10.5 | $0.0095 | **9.5%** | 1.9% |
| 5x | $17.5 | $0.0158 | **15.8%** | 3.2% |
| 8x | $28.0 | $0.0252 | **25.2%** | 5.0% |
| 12x | $42.0 | $0.0378 | **37.8%** | 7.6% |
| 15x | $52.5 | $0.0473 | **47.3%** | 9.5% |

4. **Break-even WR shifts upward as fees grow.** Canonical formula (Babypips): `BE_WR = SL / (TP + SL)`. With fees, the EFFECTIVE stop = $0.10 + fee, and effective TP = R-multiple × $0.10 − fee. At our system R:W ≈ 3.2:1 (~$0.32 avg TP target), unadjusted BE-WR ≈ 24%. Adjusted:

| Leverage | Effective SL | Effective TP | Fee-adj BE-WR | Δ vs zero-fee 24% |
| --- | --- | --- | --- | --- |
| 5x | $0.116 | $0.304 | 27.6% | +3.6 pp |
| 8x | $0.125 | $0.295 | 29.8% | +5.8 pp |
| 15x | $0.147 | $0.273 | 35.0% | +11.0 pp |

5. **Implication for current edge:** our verified WR ≈ 0.50 still clears the 35.0% bar at 15x with margin to spare — system is NOT broken. BUT the safety margin (50% − 35% = 15 pp) at 15x is now HALF what it was yesterday (50% − 26% = 24 pp at 1R=$0.50). High-leverage trades have become more fee-sensitive at the new risk level.

6. **Expectancy-in-R after fees (worked):** at 15x, fee = 0.473R. Net E shrinks from +0.39R (zero-fee) to roughly **+0.36R per trade at 5x, +0.30R at 8x, +0.20R at 15x**. Daily 13 trades × +0.20R × $0.10 = **+$0.26/day at 15x mix** vs +$0.51/day at 5x mix — confirms high-leverage tiers are LEAST profitable per-trade once fees enter the calc.

**Speculative (label as such — no published source specific to our setup):**

- Whether decimal-priced perps actually fill at advertised mid in our scalp horizon — real slippage adds ON TOP of fees and is not in the above table. Industry-consensus is decimal alts slip 1–3 ticks on market exits during fast moves; needs our own pre/post fill analysis.
- Whether reducing the leverage ceiling below 15x would mechanically restore the post-fee expectancy — math says yes, but the user has explicitly locked the 2-15x ladder; this is a NOTE for the user, not an action.
- Whether maker-only entry orders (limit at entry_zone bid) would meaningfully cut burden — math says round-trip mixed fees ~30% lower than all-taker. Would require strategy-agent to default to LIMIT entries, which can miss fills. Trade-off study needed.

**Action recommendations (NO risk-param changes; user-decision queued):**

1. **Top-priority diagnostic-only (queue for user OK, NOT auto-applied):** add `fee_burden_pct_of_1R` field to every trade-proposal logged by strategy-agent and to every journal entry. Pure observation; lets the user SEE the leverage-fee tradeoff in real time. Non-risk-touching.

2. **Lowest-effort high-impact tweak (queue for user OK):** when strategy-agent emits proposals at 12x or 15x with a noisy entry (rngpos ≥ 60% intra-1m-range), favor LIMIT entries with a 1-tick passive offset. Captures maker fee on entry (0.018% vs 0.045%) and saves ~50% of entry-side fee. Mechanic does NOT change risk params.

3. **Display-only ranking (queue for user OK):** in `/status` and daily-report output, show "edge after fees" per leverage tier so user can SEE that 15x trades return less in $ per trade than 5x trades despite higher leverage. This is an information surface, not a rule change.

**Profit-ratio implication:** if even 1 of every 4 high-leverage taker entries is shifted to maker-entry, daily fee burden drops ~12-18%. On the realized +$7.63 day, that's ~$0.10–0.15 saved — small in dollars but meaningful as a % of net daily realized (1-2 pp). The bigger insight is FRAMING: the user has implicitly raised the bar for high-leverage edge by tightening max-loss, and should know the new BE-WR thresholds before deciding whether the 12-15x tiers are still worth keeping. **No system change is needed today.**

**Risk if applied wrong:**

- Over-rotating to maker-only entries → missed fills on fast-moving scalps → strategy-agent's hit rate degrades from fill latency, not from setup quality. Mitigation: maker-preference only on noisy intra-1m entries, never on momentum breakouts where speed matters.
- Surface the fee-burden number prominently → user may anchor on it and reject high-leverage proposals that are still expectancy-positive after fees. Mitigation: pair the fee number with post-fee-expectancy-in-R, not raw fee %.
- All math assumes regular-tier fee. If user is VIP-0 with BNB discount (likely on a $40 wallet), real burden is ~10% lower than tabulated — verify before any rule.

**Status:** documented

---

## 2026-05-12T19:35Z — Alarm fatigue / cry-wolf alerts in trading and monitoring systems

**Question researched:** When a trading system repeatedly generates the same alert/verdict that does NOT result in an action (because of a downstream block, missing tool, or rejected execution), how does industry practice prevent operator and system desensitization? Specifically motivated by tonight's 7 EXIT_EARLY verdicts from `token-research-agent` that were all blocked by the missing `scripts/run_close_position.py`.

**Strongest finding (Google SRE "every page must be actionable" principle):**

Google's SRE Book (Beyer et al., O'Reilly 2016) codifies the most-cited industry rule for monitoring systems: *"Every page response should require intelligence. If a page merely merits a robotic response, it shouldn't be a page."* The corollary that applies directly to our situation: *"Can I take action in response to this alert? Is that action urgent, or could it wait until morning? Could the action be safely automated?"* — if the answer to the action question is NO, the alert must be either auto-resolved upstream or suppressed, never repeated. Source: https://sre.google/sre-book/monitoring-distributed-systems/, https://sre.google/sre-book/being-on-call/

**Quantified failure mode (alert-fatigue literature):**

1. **Operator-ignore rate at ~30%.** IDC report (via Stamus Networks summary): "large organizations ignore around 30% of alerts" once volume exceeds processing capacity. Source: https://www.stamus-networks.com/blog/the-hidden-risks-of-false-positives-how-to-prevent-alert-fatigue-in-your-organization

2. **Cost-per-false-positive ~32 minutes of investigator time.** Same Stamus summary — each non-actionable alert eats half an analyst-hour. Direct analog: every EXIT_EARLY verdict that token-research-agent emits but cannot fire still costs (a) an LLM token spend, (b) the user's attention if surfaced, (c) trust erosion in subsequent verdicts.

3. **Tenth-false-alarm threshold.** Crytica Security / OT-control-room consensus: *"after the tenth false alarm, the urgency fades, and operators stop dropping everything to investigate."* Tonight's count was 7 in a single session — we are within 30% of the canonical desensitization knee. Source: https://www.cryticasecurity.com/blog/false-positives-and-alert-fatigue-what-you-need-to-know

4. **51% of SOC teams overwhelmed; 25% of analyst time on false positives.** Trend Micro 2024 survey via IBM. Most-cited mitigation: **deduplication windows + actionability gating + severity tiering.** Source: https://www.ibm.com/think/topics/alert-fatigue

5. **Trading-specific evidence (Tyler Capital HRO case, PMC 8978471):** the authors flag that algorithmic-trading firms struggle with the *response-time* gap between automated alert generation (microseconds) and human kill-switch decision (~30 minutes). They do NOT solve the cry-wolf problem explicitly — confirming it as an *understudied* failure mode in algorithmic trading, distinct from but more dangerous than in healthcare/SOC because the underlying market state moves while the operator waits. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC8978471/

**Today's empirical match (tonight's session, 2026-05-12):**

- `token-research-agent` emitted 7 EXIT_EARLY verdicts on positions at r_curr ≤ −0.3R.
- ALL 7 were blocked because `scripts/run_close_position.py` does not exist (Phase 1 fix queued).
- Net effect: the loss-research agent ran, spent LLM tokens, produced verdicts, and the verdicts were dropped on the floor. This is *exactly* the cry-wolf failure mode the SRE literature warns about: a signal that fires without consequence trains both the system and the operator to discount the next signal of the same type.
- Compounding risk: if the user sees "EXIT_EARLY verdict — execution unavailable" 7 times in one night, the 8th *real* verdict gets discounted as another false alarm. This is the documented "tenth-alarm threshold" approaching.

**Mapping to our locked policy:**

- Locked policy is NOT touched. Margin 3.5, leverage 2-15x conf-gated, max planned loss $0.10 STRICT, min conf 0.75, daily cap $4.0 day, max open 8 — all unchanged.
- Finding affects *execution-pipeline reliability and signal hygiene*, not risk parameters. Fits into the safety-and-discipline layer that the policy explicitly mandates.

**Speculative (label as such):**

- Whether the EXIT_EARLY verdicts that fired tonight would have been profitable to act on — we can only know after the missing `run_close_position.py` exists AND a comparison cohort runs. Until then we cannot quantify the "saved loss" or "missed save" magnitude.
- Whether 7 blocked verdicts in one session is a one-off (script missing → easy fix) or a class of failure (signals routinely outrun execution capability) — needs ≥ 1 more session post-Phase-1-fix to determine.
- Whether the giveback-protection cron and the loss-research cron will *both* fire on the same position (double-alert) — design review needed; not yet observed in trade-events.jsonl.

**Action recommendations (NO risk-param changes; pipeline hygiene only):**

1. **Highest priority — already queued: Phase 1 fix to ship `scripts/run_close_position.py`.** This converts EXIT_EARLY verdicts from cry-wolf alerts into actionable closures. The SRE "every page must be actionable" rule says this is non-negotiable: signals that cannot result in action must either auto-resolve or be suppressed at source. Queue to error-fix-agent ONLY with explicit user OK (already implicit per Phase 1 plan).

2. **Add a deduplication / suppression window.** SRE-canonical pattern: if `token-research-agent` emits EXIT_EARLY for the same position twice within 10 min, the second verdict should not re-trigger an LLM call OR a user-visible alert — it should silently update the existing pending action. Prevents the 7-strikes-in-one-session cascade. Diagnostic field needed in `data/loss-research-log.jsonl`: `dedup_window_minutes` + `dedup_key = symbol+position_id`. NOT risk-touching.

3. **Add a "verdicts-blocked-by-missing-tool" counter to `/status` output.** If the number is non-zero, surface it prominently so the user (or any cron) can see the cry-wolf failure mode building. Currently this metric does not exist — tonight's 7 blocks were only visible via grep of run logs. Pure observation, NO risk param touched. Queue for user OK.

4. **Adopt the actionability gate as a code-review rule for any future agent that emits verdicts:** before merging the agent, the agent's output must be either (a) directly executable by a named, existing script, or (b) explicitly tagged `advisory_only=true`. Prevents future cry-wolf agents from shipping with unmet downstream dependencies. Documentation change only, NOT risk-touching.

**Profit-ratio implication:**

- The 7 blocked EXIT_EARLY verdicts tonight are unknown-quantity at this point. If the average verdict would have saved 0.3R per position ($0.03 at tightened 1R = $0.10), the loss-prevention value is ~$0.21 — small.
- The REAL benefit of fixing cry-wolf is *signal trust preservation*. Once the user starts ignoring EXIT_EARLY verdicts because "they never fire anyway," the next legitimate verdict gets ignored too — and that one might be the position headed to a $2-5 USDT max-adverse excursion. The catastrophe-prevention value is asymmetric and large.
- Order-of-magnitude estimate: avoiding ONE late-recognized loss per month that would have gone to −$3.00 instead of −$0.50 = +$2.50/month preserved = +$0.08/day. Small in $, but the same fix preserves trust in the entire monitoring layer.

**Risk if applied wrong:**

- **Over-suppression.** If the dedup window is too long (e.g., 1 hour), a fast-deteriorating position emits ONE verdict at minute 0, then drifts further south at minute 30 — but the second verdict gets suppressed under "same dedup key." Mitigation: dedup should suppress duplicate alerts BUT allow upgraded severity (e.g., r_curr = −0.3R suppressed, but r_curr = −0.6R fires fresh).
- **False sense of fix.** Shipping `run_close_position.py` removes the *visible* cry-wolf symptom but doesn't fix the root cause (agent emits before checking executability). Mitigation: the actionability gate (item 4) treats the symptom AND the class.
- **User over-trusts post-fix verdicts.** If we fix cry-wolf, the next batch of EXIT_EARLY verdicts will fire real closures. If the verdict quality is poor (lots of false-positive EXITs on noise dips), we'll have converted cry-wolf into cry-actual-loss. Mitigation: log every executed EXIT_EARLY verdict's t+30min PnL to detect false-positive verdicts BEFORE they cumulate into a losing pattern.

**Status:** documented; Phase 1 fix already queued; items 2-4 are non-risk-touching pipeline hygiene proposals awaiting user OK.

---

## RESEARCH-2026-05-12T22:00:00Z

**Question (queue item #1, on-rotation):** Market-regime classification — what is a practical taxonomy *beyond* "mixed / trending / ranging" for our 5-15 min scalp horizon on Binance USDT-M decimal-priced perps? What indicators + thresholds + per-regime strategy adjustments are documented? Can we ship a deterministic regime tag (label-only, no auto-filter) to enrich proposal context?

**Sources reviewed:**
- LuxAlgo, "Market Regimes Explained: Build Winning Trading Strategies" — https://www.luxalgo.com/blog/market-regimes-explained-build-winning-trading-strategies/
- QuantMonitor, "How to Identify Market Regimes and Filter Strategies by Trend and Volatility" — https://quantmonitor.net/how-to-identify-market-regimes-and-filter-strategies-by-trend-and-volatility/
- Thrive, "Crypto Market Regime Detection" — https://thrive.fi/blog/trading/crypto-market-regime-detection
- Preprints.org (Bitcoin 2024–2026), "Markov and Hidden Markov Models for Regime Detection in Cryptocurrency Markets" — https://www.preprints.org/manuscript/202603.0831
- TradingView (LuxAlgo HMM script reference) — https://www.tradingview.com/script/USWQEica-Hidden-Markov-Model-Market-Regimes-LuxAlgo/

**Key finding (single strong idea):** **The 2×2 trend-direction × volatility-state matrix collapses cleanly to a 4-regime taxonomy that is computable on Binance 5-min klines with two cheap indicators (SMA-50 slope sign + ATR-percentile rank), and the literature attaches *strategy-selection* rules to each cell — not blanket position-size scaling.** For us this means a **proposal-context tag** (`regime: UP_LOWVOL | UP_HIGHVOL | DOWN_LOWVOL | DOWN_HIGHVOL | RANGE`) is the highest-leverage diagnostic-first artifact. It does not change margin, max-loss, or min-confidence; it logs the regime active at entry, allowing later scatterplot of WR × regime × strategy-type to surface where our current setup is mismatched to the market state.

**Established (cited, multi-source-corroborated):**

1. **2×2 trend × vol matrix is the canonical practitioner taxonomy** (LuxAlgo + QuantMonitor convergent). QuantMonitor specifically reports backtest filter where `(SMA(50)[0] - SMA(50)[5]) > 0 AND ATR(14)/Close < MA(ATR%, 100)` enables strategy ~95% of bars in `Up_LowVol` regime, ~59% in `Up_MidVol` / `Up_HighVol`, and 0% in all `Down_*` regimes. Translation: **trend-following long-only strategies are documented to harvest most of their edge in `Up_LowVol`**. Source: https://quantmonitor.net/how-to-identify-market-regimes-and-filter-strategies-by-trend-and-volatility/

2. **Indicator thresholds (Thrive, explicit numeric):**
   - **ADX**: < 20 = no trend (range), 20–40 = developing, > 40 = strong trend, > 60 = exhaustion-watch.
   - **ATR-percentile (252-period lookback)**: < 0.20 = low vol regime; 0.20-0.80 = normal; > 0.80 = high vol.
   - **MA slope (20-period)**: < 0.005 with MA separation < 0.02 = ranging; > 0.02 = uptrend; < -0.02 = downtrend.
   - **Bollinger Band Width**: low BBW = squeeze (breakout imminent); high BBW = elevated volatility.
   Source: https://thrive.fi/blog/trading/crypto-market-regime-detection

3. **Per-regime strategy adjustments (Thrive table):**
   | Regime | Position Sizing | Stop Placement | Entry Method |
   | --- | --- | --- | --- |
   | Trending | 100% | swing lows/highs | MA pullback |
   | Ranging | 50-75% | beyond boundaries | S/R touch |
   | Volatile | 25-50% or flat | wide or none | extreme readings only |

4. **LuxAlgo win-rate framing (caveats apply — likely overoptimistic for our horizon):** trend-following in trending regime quoted at 20-40% WR with R:W skew; mean-reversion in ranging regime quoted at 80-85% WR with smaller R:W. Quoted impact of regime-aware strategy switching: **+10-30% risk-adjusted return improvement, drawdown cut by similar margin**, with one cited HMM strategy delivering 36% return / Sharpe 1.7 / max DD 7.3%. Source: https://www.luxalgo.com/blog/market-regimes-explained-build-winning-trading-strategies/. *Caveat: numbers are multi-asset across daily/4h timeframes; transfer to 5-15 min Binance scalps is unverified.*

5. **HMM-based regime detection is the academic state-of-the-art** (Preprints.org, 2024–2026 Bitcoin study). 3-state models (low-vol / high-vol / distress) and 5-state models (Bitcoin volatility-clustering + jump-asymmetric transitions) cited as optimal. Source: https://www.preprints.org/manuscript/202603.0831. **Not recommended for us** — HMM requires fit/retrain cadence + numeric stability + large feature engineering; ROI vs simple 2×2 matrix is unproven at our wallet size.

**Speculative (label as such):**

- Whether the 5-15 min ATR percentile transfers cleanly to small-cap decimal-priced perps. Decimal coins likely show fat-tailed ATR-%-of-price distributions vs majors → 80th percentile cutoff may be loose. Needs our own percentile computation per-symbol, not blanket.
- Whether SMA-50 slope on 5-min candles is fast enough to label regime at scalp entry. Slower MA → label lags real regime; faster MA → label whipsaws. EMA(20) slope is a plausible alternative; no peer-reviewed evidence isolates the right anchor for 5-15 min holds.
- Whether our existing "rngpos" feature already captures most of the range-vs-trend information that an ADX-based regime tag would add. Could be heavily collinear, and the simpler feature wins.
- Whether ranging regime (per LuxAlgo's 80-85% WR / mean-reversion numbers) is realistically achievable at our R:W of ~1:3.2 — most cited ranging strategies use R:W ≤ 1:1.5. Adopting mean-reversion would force a different R:W regime our system isn't currently configured for.

**Today's empirical match (2026-05-12 night):** The 6+ hour safety pause + 7 cry-wolf EXIT_EARLY events + USELESSUSDT $14 intraday swing all point to **regime-shift events the agency does not currently flag.** There is no `regime_at_entry` field on any trade-journal record; we cannot now retrospect whether our 30% loss-rate trades clustered in `Down_HighVol` or `Up_HighVol`. This is the bottleneck.

**Mapping to locked policy (context tag + diagnostic only, NOT a filter or risk-param change):**

- Add `regime_at_entry` field to trade-journal records (one of: `UP_LOWVOL | UP_HIGHVOL | DOWN_LOWVOL | DOWN_HIGHVOL | RANGE`).
- Computed at proposal-time from Binance 5-min klines for the proposal symbol:
  - `trend_sign`: sign of `(SMA(50)[0] - SMA(50)[5])` (LONG / SHORT / FLAT, with FLAT = abs slope < 0.05% of price).
  - `vol_state`: percentile rank of current ATR(14)/Close over last 252 candles (~21 hours at 5-min). LOW = < 20th, NORMAL = 20-80, HIGH = > 80th.
  - Combine: trend_sign × vol_state → 4 quadrants; FLAT trend → `RANGE` regardless of vol.
- No filter applied. No confidence nudge applied. Pure observation infrastructure. Margin 3.5, leverage ladder 2-15x, max-loss $0.10, daily cap $1.0, max-open 8, min-conf 0.75 — ALL UNCHANGED.

**Action recommendations (NO risk-param changes; user-decision queued):**

1. **Diagnostic-first: ship `regime_at_entry` field** via `scripts/regime_tag.py` invoked from proposal pipeline. Tag is written to trade-journal records + proposal context. Non-risk-touching. Queue to error-fix-agent ONLY with explicit user OK.

2. **After ≥ 30 trades with regime tag attached, scatterplot WR × regime × strategy-type.** Likely outcome (hypothesis): our breakout/momentum strategies cluster wins in `UP_HIGHVOL` and losses in `DOWN_HIGHVOL` and `RANGE`. If confirmed, the next-stage proposal is a `regime × strategy-type` confidence-nudge table — NOT a hard filter.

3. **Optional companion: `/status` displays current `regime_at_entry` for BTC** (proxy for crypto-wide regime) so the user has a glance-readable market-state indicator even before trade-level regime tagging matures.

4. **NOT recommended:** auto-rejecting any proposal based on regime. Literature numbers (LuxAlgo's +10-30% lift) are multi-asset daily/4h — direct transfer to 5-15 min decimal-perp scalps is unverified. Diagnostic-first preserves trade count while building the dataset to justify any future rule.

5. **NOT recommended:** HMM/ML-based regime classifier. Too much code surface for our wallet size; 2×2 trend × vol matrix captures most of the available signal with two indicators.

**Profit-ratio implication (hypothesis, needs-validation):** If regime tagging surfaces a single high-loss-rate quadrant accounting for ~25% of trades, and a future filter rejects/de-weights that quadrant: ~+$0.10-0.30/day expected lift after ≥ 30-trade calibration. Independence from rngpos/funding/OI/news-calendar/ATR signals is MEDIUM — vol-state correlates with ATR overlay, but trend-sign is orthogonal. Primary value is **diagnostic visibility** (currently zero), not immediate return enhancement. Does NOT independently close gap to $10/day.

**Risk if applied wrong:**

- **Tagging-only is safe**; no risk of misexecution from a logged field.
- **Threshold drift on decimal-perp ATR percentile.** 252-candle lookback = ~21 hours on 5-min — short for some decimal coins that go quiet for days then spike. Mitigation: bucket per-symbol percentile, not cross-symbol blanket.
- **SMA-50 lag.** 50 × 5-min = 4.2-hour anchor on a 5-15 min trade. Could label `UP_*` when a fresh reversal is mid-flight. Mitigation: pair SMA-50 slope with EMA(20) cross as a confirmation, or downgrade trend confidence when EMA-20 is below SMA-50 in an UP_* regime.
- **Premature filter adoption.** If a future contributor reads the regime tag and adds a filter before 30-trade calibration, we risk over-cutting trade count on small-sample bias. Mitigation: explicit "diagnostic-only, no filter until N=30" comment in the code path.

**Status:** documented; recommendation #1 (diagnostic-only `regime_at_entry` infrastructure) queued for user OK before any orchestrator → error-fix-agent spawn. Rotation queue: item #1 (Market-regime classification) moves to bottom; next fire takes item #2 (Profit-target optimization, but flagged "revisit after material wallet/edge change" — skip to item #3 Scalp-exit research, also flagged → next un-cooldown is item #2 list-position-relative; in practice the next-eligible topic is the first one whose cooldown has expired).

---

## 2026-05-12T22:35Z — Liquidation-cluster magnets + CVD-divergence confirmation (NEW topic, off-queue: all 10 rotation items currently cooldown-gated)

**Topic:** Liquidity-heatmap / liquidation-cluster entries paired with CVD-divergence confirmation, as a complementary signal class to our microstructure stack (rngpos / funding / OI / regime / ATR).

**Rotation context:** All 10 enumerated rotation items currently have explicit cooldown gates (N≥30 trades with new diagnostic field, post-implementation deltas, or material wallet/edge change). Picking the next un-cooldown item would require waiting. Instead, opening a NEW slot in the topic library with this fire, with explicit user-facing flag that this is an additive eleventh slot (not a queue jump).

**Sources reviewed (5):**

1. **Zipmex 2026 guide — liquidation heatmap mechanics, magnet effect, and sweep-and-reverse:** https://zipmex.com/blog/what-is-a-liquidation-heatmap/
2. **Coinglass Pro futures liquidation heatmap (primary live data tool referenced across the literature):** https://www.coinglass.com/pro/futures/LiquidationHeatMap
3. **Glassnode Insights "Pressure Points: Liquidation Heatmaps & Market Bias" (analytical framework, NO quantified thresholds):** https://insights.glassnode.com/liquidation-heatmaps/
4. **Bookmap CVD-divergence scalping guide (definition, reference-level + reaction-confirmation requirement, NO numeric thresholds):** https://bookmap.com/blog/how-cumulative-volume-delta-transform-your-trading-strategy
5. **Phemex Academy CVD ultimate guide + LuxAlgo CVD page (corroboration of divergence definition + scalp 5-15 min applicability):** https://phemex.com/academy/what-is-cumulative-delta-cvd-indicator, https://www.luxalgo.com/blog/cumulative-volume-delta-explained/

**Established (cited, multi-source-corroborated):**

1. **Liquidation clusters behave as price magnets in advance of being swept.** The mechanism: when many leveraged traders share similar liquidation thresholds, those zones become structurally fragile; price tends to drift toward them because market makers/aggressors who can see the cluster will probe it. Sources: Zipmex (explicit "magnet" language), Glassnode (more cautious "pressure points / structurally fragile" framing — declines to call them magnets explicitly).

2. **Sweep-and-reverse is the cited canonical setup.** Once a cluster is triggered (swept by a wick or rapid move), the forced closures briefly amplify price in the trigger direction, after which the magnet *disappears* and price often reverses sharply. Source: Zipmex explicit; Glassnode shows the cascade direction-only and does NOT confirm the reverse leg (caveat).

3. **CVD divergence is the cleanest off-the-shelf confirmation signal for sweep-and-reverse.** Definition (Bookmap, Phemex, LuxAlgo convergent):
   - **Bullish divergence:** price makes lower low, CVD makes higher low or stabilizes — selling losing control, absorption forming.
   - **Bearish divergence:** price makes higher high, CVD makes lower high or stalls — aggressive buying not confirming the move.
   The pattern operationalizes the literature's "sweep + reaction" requirement: cluster sweep prints the price extreme; CVD failing to follow prints the divergence; the combined event is the entry trigger.

4. **Scalp horizon is explicitly endorsed for CVD.** Bookmap + Phemex: 5–15 min charts work well for CVD-divergence scalp entries because CVD updates in real time and short-window absorption/exhaustion is exactly what the indicator surfaces. **Direct fit for our 5–15 min hold horizon.**

5. **Required confirmation stack (Bookmap explicit):**
   - (a) Divergence must occur **at a known reference level** (prior high/low, VWAP, visible liquidity zone — exactly where a liquidation cluster lives).
   - (b) **Wait for a reaction** (failure to continue + shift in CVD direction) before treating as actionable.
   - (c) **Volume alignment**: high-volume divergence carries more weight than low-volume.
   - (d) **Multi-indicator confluence** (RSI/MACD/Volume Profile) further filters false signals.

**Speculative (label as such):**

- **No published numeric threshold for "significant" cluster size, sweep depth, or CVD-divergence magnitude.** Glassnode is explicit: their report is analytical framework, not executable rules. Empirical thresholds must come from our own backtest.
- **Coinglass-style aggregate heatmaps weight major coins.** Decimal-priced small-cap alts (BILL, UB, NAORIS, SAGA, SKYAI tier) often lack visible cluster data because aggregate OI is too small to chart meaningfully. Direct transfer of the BTC sweep-and-reverse pattern to our universe is UNVERIFIED. The pattern may degrade to noise on names where 90% of open interest sits in 1–2 wallets.
- **The reverse leg of sweep-and-reverse is asymmetric in the literature.** Zipmex asserts it; Glassnode does NOT. Treat as 60-70% confidence pattern, not 95%.
- **CVD divergence on Binance USDT-M perps at the 5-min horizon has no peer-reviewed backtest specific to small-cap decimal coins.**
- **Liquidation heatmap data access cost.** Coinglass Pro requires a paid tier for symbol-level granularity beyond BTC/ETH. Free tier won't cover our universe.

**Today's empirical match (2026-05-12 night):** USELESSUSDT $14 intraday swing from MFE +$1.56 to subsequent give-back exit happened in a session where neither a liquidation-cluster overlay NOR a CVD-divergence read were available to any agent. Whether the swing's reversal point aligned with a swept cluster + bearish-CVD-divergence is **unverifiable now** because we log neither. Same applies to FHE / BUSDT BE-trail give-backs.

**Mapping to locked policy (diagnostic-only context tag, NOT a filter or risk-param change):**

- Add `liquidation_context_at_entry` field to trade-journal records, one of: `BELOW_LONG_CLUSTER | ABOVE_SHORT_CLUSTER | INSIDE_CLUSTER_ZONE | NO_NEARBY_CLUSTER | DATA_UNAVAILABLE`.
- Add `cvd_5m_divergence_at_entry` boolean field + `cvd_direction` (`BULLISH | BEARISH | NEUTRAL`) computed from Binance trade-flow API or `klines` taker-buy ratio over the last 12 × 5-min candles.
- Pure observation. No filter. No confidence nudge. No risk-param change. Margin 3.5 / leverage 2-15x / max-loss $0.10 / daily-cap $1.0 / max-open 8 / min-conf 0.75 ALL UNCHANGED.

**Action recommendations (NO risk-param changes; user-decision queued):**

1. **Diagnostic-first (HIGH-VALUE, LOW-CODE):** add `cvd_5m_at_entry` derived from Binance `/fapi/v1/klines` `takerBuyVolume` field — already in the response we fetch, no extra API call. Compute over last 12 candles (60 min): `cvd_5m = sum(2*takerBuyVolume - totalVolume)`. Sign + slope = direction + divergence-vs-price signal. Tag onto every proposal + journal record. Queue to error-fix-agent ONLY with explicit user OK.

2. **Diagnostic-second (HIGHER-CODE, EXTERNAL DEP):** add `liquidation_context_at_entry` via Coinglass public-API or scraping (rate-limited; needs caching). Lower priority because (a) data quality on our decimal-perp universe is uncertain and (b) the field can be `DATA_UNAVAILABLE` on most of our trades, weakening empirical analysis. Defer until ≥ 50 CVD-tagged trades exist and CVD-tag itself shows a signal worth augmenting.

3. **After ≥ 30 trades with CVD-divergence tag attached, scatterplot:** WR × {divergence-at-entry: yes/no} × {direction: with / against price trend}. Hypothesis: trades entered AGAINST CVD direction (e.g. LONG when CVD bearish-diverging) cluster in negative-EV quadrant. If confirmed, propose CVD-direction-aware confidence nudge — NOT a hard filter.

4. **NOT recommended:** auto-rejecting any proposal on CVD-divergence alone. Bookmap explicit: divergence is "not a standalone signal." Mitigation: tag-only + require ≥ 30 trades + nudge-not-filter.

5. **NOT recommended:** paid Coinglass Pro subscription. Cost likely exceeds expected lift on our 30-USDT wallet. Free-tier BTC/ETH cluster data can be used as a *cross-asset regime tag* (when BTC sweeps a major cluster, our alt-scalp false-signal rate likely rises) — that's a different, simpler use case.

**Profit-ratio implication (hypothesis, needs-validation):** If CVD-divergence tag catches the give-back-prone setups responsible for ~15% of trades in negative-EV quadrant, and a future confidence-nudge filter de-weights them: ~+$0.15-0.30/day expected lift after ≥ 30-trade calibration. Independence from rngpos/funding/OI/news-calendar/ATR/regime signals is MEDIUM — CVD is a delta/flow signal whereas rngpos is range-position, funding is fee-flow, OI is positioning, ATR is volatility, regime is trend × vol; CVD adds the *aggressive-side* dimension none of the others capture. Does NOT independently close gap to $10/day.

**Risk if applied wrong:**

- **Computing CVD from 5-min taker-buy aggregates is a proxy, not true tick-level CVD.** Real CVD requires trade-by-trade data; the 5-min aggregate misses intra-candle absorption. Mitigation: label our field `cvd_5m_approx` to avoid implying tick precision; flag in code that true CVD requires `/fapi/v1/aggTrades` if precision becomes load-bearing.
- **CVD on thin-book decimal coins is noisier than on majors.** A handful of large taker prints can dominate the read. Mitigation: bucket diagnostic by `notional_volume_5m`; consider rejecting CVD signal when 5-min volume is below a per-symbol median.
- **Liquidation-cluster data unavailability for most of our universe.** Mitigation: explicit `DATA_UNAVAILABLE` enum value; analysis must condition on `liquidation_context_at_entry != DATA_UNAVAILABLE` when scatterplotting.
- **Compounding signals could compress trade count from ~13/day to ~3-4/day.** Mitigation: staged rollout, measure delta after each new signal, abort additional layers if trade count drops below 8/day.
- **Confirmation-bias risk on giveback-prone trades.** Operator could read a CVD tag retrospectively to justify EXIT_EARLY before the diagnostic threshold is calibrated. Mitigation: lock the rotation policy ("no live decisioning until N=30 + scatterplot review").

**Status:** documented as the 11th slot in the topic library (NEW topic, not a queue jump — all 10 enumerated rotation items currently cooldown-gated). Recommendation #1 (diagnostic-only `cvd_5m_approx` infrastructure derived from existing `/fapi/v1/klines` response, zero extra API call) queued for user OK before any orchestrator → error-fix-agent spawn. Rotation queue position UNCHANGED — when cooldown gates expire on items #1-#10, normal rotation resumes; this slot becomes #11 with first-research cooldown of "≥ 30 trades with `cvd_5m_approx` field attached" before revisit.

---

