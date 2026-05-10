# Strategy Memory

Per-strategy performance tracked by the Strategy and Learning Agents.

## Strategies Tracked

- long_breakout
- short_breakdown
- pullback
- momentum_continuation
- failed_breakout_short
- short_after_pump
- reversal_scalp
- range_trade

## Format

```
## STRATEGY_NAME

- Version: vN
- Sample size: N
- Win rate: %
- Avg PnL (USDT): X
- Avg PnL %: X
- Best regime: [bullish | bearish | mixed | volatile]
- Worst regime: [list]
- Common failure mode: [text]
- Last updated: yyyy-mm-dd
```
