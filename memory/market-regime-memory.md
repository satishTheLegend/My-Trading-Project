# Market Regime Memory

Daily market regime classification tracked by the Market Intelligence Agent.

## Format

```
## yyyy-mm-dd

- Regime: bullish | bearish | mixed | sideways | volatile | dangerous | no_trade
- BTC bias:
- ETH bias:
- Volatility: low | medium | high | extreme
- Risk level (0-10):
- News notes:
- Trades that day: count, win rate, net PnL
- Hindsight note: did the regime call match outcomes?
```

## 2026-05-10

- Regime: volatile (small-cap pump environment; BTC sideways)
- BTC bias: neutral (BTC 1h change -0.17%, price ~81240 USDT)
- ETH bias: unknown (not checked directly this cycle)
- Volatility: high (top screened candidates had 17-28% 24h moves; PONKEUSDT +28%, HIPPOUSDT +27%, UBUSDT +21%)
- Risk level: 6
- News notes: no news shock detected; BTC stable; small-cap tokens in active pump phase
- Trades that day: 0 executed, 0 paper positions opened; multiple trade-decision and risk rejections
- Hindsight note: pending (no trades to evaluate)
