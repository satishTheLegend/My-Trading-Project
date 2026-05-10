# Token Memory

Per-symbol notes accumulated by the Token Research Agent and Learning Agent.

## Format

```
## SYMBOL (e.g., DOGEUSDT)

- Last reviewed: yyyy-mm-dd
- Liquidity: low | medium | high
- Spread quality: good | average | poor
- Typical volatility: low | medium | high
- Best strategies: [list]
- Worst strategies: [list]
- Avoid until: yyyy-mm-dd or "—"
- Recent outcomes: [date — strategy — net PnL — note]
- User notes: [free text]
```

## Index

<!-- Auto-maintained list of symbols below -->

## PONKEUSDT

- Last reviewed: 2026-05-10
- Liquidity: high (3.53B USDT 24h volume)
- Spread quality: unknown (order book not sampled)
- Typical volatility: high (28% 24h move, ATR 5.5% on 1h)
- Best strategies: failed_breakout_short (when at resistance)
- Worst strategies: long_breakout (too extended from resistance), momentum_continuation (volume insufficient)
- Avoid until: --
- Recent outcomes: [2026-05-10 -- failed_breakout_short -- NOT TRADED -- confidence 0.55, below MIN_CONFIDENCE threshold]
- User notes: Decimal-priced, highly liquid. Was 21% above nearest support. 1h RSI 64, 15m RSI 60. Not ideal for entry today -- too far from support/resistance zones.

## HIPPOUSDT

- Last reviewed: 2026-05-10
- Liquidity: medium (619M USDT 24h volume)
- Spread quality: poor (spread 32 bps, exceeds 20 bps threshold -- triggered no-trade)
- Typical volatility: high (27% 24h move, ATR 4.3% on 1h)
- Best strategies: pullback_long (if spread improves)
- Worst strategies: long_breakout, momentum_continuation
- Avoid until: --
- Recent outcomes: [2026-05-10 -- pullback_long -- NOT TRADED -- spread 32 bps triggered no-trade filter]
- User notes: Spread too wide for safe entry. Price at 0.0003130. 1h RSI 62, 15m RSI 54. Good uptrend structure but spread disqualifies.

## UBUSDT

- Last reviewed: 2026-05-10
- Liquidity: high (1.49B USDT 24h volume)
- Spread quality: poor (spread 23 bps, slightly above 20 bps threshold)
- Typical volatility: high (21% 24h move, ATR 2.6% on 1h)
- Best strategies: short_after_pump (detected today with conf 0.65-0.70)
- Worst strategies: long_breakout
- Avoid until: --
- Recent outcomes: [2026-05-10 -- short_after_pump -- REJECTED BY RISK -- MIN_NOTIONAL 5 + stop 2.2% + max_loss 5% constraint incompatible with <2 USDT margin account]
- User notes: Good setup quality today (RSI 1h=75, 15m=72, multi-hour pump detected) but wallet/MIN_NOTIONAL mismatch prevents entry. Funding rate elevated at 0.00032. Watch for potential re-entry opportunity when risk constraints are resolved.
