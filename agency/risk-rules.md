# Risk Rules

## Default Risk Parameters

- Wallet context: around 10 USDT.
- Max margin per trade: 1–2 USDT by default.
- Preferred leverage: 2x–5x.
- Max planned loss: approximately 5% of margin used.
- Preferred margin mode: isolated.
- Max open positions: 1–2 initially.
- Daily loss limit: 10–15% of wallet.
- Stop after 2–3 consecutive losses.
- No duplicate symbol positions.
- No averaging down by default.
- No revenge trading.

## Trade Rejection Conditions

Reject trade if:
- No stop/invalidation.
- Stop distance too large.
- Liquidation too close.
- Spread too high.
- Liquidity too weak.
- Expected profit after fees too small.
- Funding risk too high.
- Quantity cannot satisfy Binance filters safely.
- Risk/reward poor.
- Confidence below threshold.
- BTC/ETH regime conflicts with setup without strong reason.
- Recent losses indicate bad conditions.
- Strategy underperforms in current regime.

## Leverage Rule

Leverage is not based only on confidence.

Leverage must be based on:
- Stop distance.
- Liquidation distance.
- Volatility.
- Liquidity.
- Wallet size.
- Margin risk.
- Strategy quality.
- Market regime.

## Profit Rule

Profit target must cover:
- Entry fee.
- Exit fee.
- Expected slippage.
- Funding if applicable.
- Previous loss recovery only if setup quality remains strong.

Do not force recovery trades.
