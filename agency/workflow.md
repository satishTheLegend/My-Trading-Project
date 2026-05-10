# Complete Trading Workflow

## Workflow Name

Binance Futures AI Trading Agency Full Cycle

## Trigger

Triggered by:
- `/start-trading-workflow`
- `/paper-trade-cycle`
- `/live-trade-cycle`
- User asking to scan, research, trade, execute, monitor, or report.
- Watcher Agent detecting open positions requiring monitoring.

## Workflow Steps

### Step 1: Safety Check

Safety/Kill-Switch Agent checks:
- System mode.
- API health.
- Market data health.
- WebSocket health.
- Open position state.
- Daily loss.
- Consecutive losses.
- Wallet threshold.
- Whether new trades are allowed.

If unsafe, pause new trades.

### Step 2: Market Intelligence

Market Intelligence Agent checks:
- BTC trend.
- ETH trend.
- Global market regime.
- Crypto news.
- Volatility.
- Direction preference.
- No-trade conditions.

Output:
- Bullish
- Bearish
- Mixed
- Volatile
- Dangerous
- No-trade

### Step 3: Token Screening

Token Screener Agent scans Binance USDT-M Futures:
- Small-cap/decimal candidates.
- Volume.
- 24h change.
- Spread.
- Liquidity.
- Volatility.
- Already-open symbols.
- Abnormal movers.

Output:
- Candidate list.
- Rejected list.

### Step 4: Token Research

Token Research Agent deep researches top candidates:
- Candles.
- Yesterday close.
- Today open/high/low.
- Support/resistance.
- Volume.
- Funding.
- Open interest if available.
- Order book.
- News.
- Token memory.

### Step 5: Strategy Selection

Strategy Agent chooses:
- Long breakout.
- Short breakdown.
- Pullback.
- Momentum continuation.
- Failed breakout short.
- Short after pump.
- Reversal scalp.
- No-trade.

### Step 6: Trade Decision

Trade Decision Agent compares opportunities:
- Pick best trade.
- Wait.
- Reject all.

Creates proposal only if quality is strong.

### Step 7: Risk Approval

Risk Manager checks:
- Wallet.
- Margin.
- Leverage.
- Stop distance.
- Liquidation.
- Spread.
- Slippage.
- Fees.
- Funding.
- Daily loss.
- Consecutive loss.
- Open exposure.

Approves, rejects, reduces size, lowers leverage, or waits.

### Step 8: Position Sizing

Position Sizing Agent calculates:
- Margin.
- Leverage.
- Notional.
- Quantity.
- Precision.
- Minimum notional.
- Fees.
- Max planned loss.

### Step 9: Execution

Execution Agent executes only if:
- Mode allows execution.
- Risk approved.
- Safety approved.
- Quantity valid.
- Stop/protection exists.

After execution:
- Confirm fill.
- Place protection.
- Report order IDs.
- Update Position Manager.

### Step 10: Position Management

Position Manager records:
- Position state.
- Entry.
- Quantity.
- Leverage.
- Margin mode.
- Stop.
- TP.
- PnL.
- Liquidation.
- Order IDs.

### Step 11: Watcher Monitoring

Watcher Agent continuously watches:
- Mark price.
- Last price.
- PnL.
- Liquidation distance.
- BTC/ETH.
- Volume.
- Candles.
- Funding.
- Stop status.
- TP progress.

### Step 12: Exit

Exit Agent decides:
- Hold.
- Partial TP.
- Full TP.
- Move stop.
- Trail stop.
- Emergency exit.
- Invalidation exit.

Execution Agent performs reduce-only exits.

### Step 13: Journal

Journal Agent records:
- Proposal.
- Risk decision.
- Entry.
- Exit.
- Fees.
- Funding.
- Net PnL.
- Strategy.
- Reason.
- Mistake tags.

### Step 14: Learning

Learning Agent updates:
- Token memory.
- Strategy memory.
- Market regime memory.
- Avoid-list.
- Improvement suggestions.

### Step 15: User Report

User Report Agent summarizes:
- Scanned tokens.
- Decisions.
- Trades.
- PnL.
- Warnings.
- Next actions.
