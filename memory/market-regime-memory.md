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
- BTC bias: neutral (BTC 1h change -0.17% early session; +0.81% by 17:25Z, price ~81359 USDT)
- ETH bias: neutral-bullish (ETH +1.12%, price ~2354 USDT)
- Volatility: high (top screened candidates had 14-36% 24h moves; PONKEUSDT +36%, HIPPOUSDT +32%, LAYERUSDT +27%, UBUSDT +19%)
- Risk level: 6
- News notes: no news shock detected; BTC stable; small-cap tokens in active pump phase; NAORISUSDT -24.57% (reversal); DEEPUSDT RSI 92 (extreme overbought); LAYERUSDT RSI 15m 37 (pullback from high)
- Trades that day: 0 executed (0 live, 0 paper); blocked by API geo-restriction on mainnet; LAYERUSDT long proposal rejected by safety-agent (API -2015)
- Hindsight note: LAYERUSDT oversold pullback setup at 12h support was structurally valid (spread 8 bps, RSI 37, 2:1 RR). Could not execute.
