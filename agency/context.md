# Agency Context

This project is a Binance Futures AI Trading Agency for automated research, decision-making, execution, monitoring, exit, journaling, and learning.

## User Background

The user trades Binance Futures small-cap and decimal-priced tokens. The user previously spent 3–4 hours per day doing analysis and 2–3 hours actively trading. The user has a small Futures wallet, around 10 USDT, and usually trades with 2x–5x leverage. The user makes roughly 10–100 USD/day manually during good trading days but wants automation to reduce repetitive attention-heavy work.

## Core Problem

Manual trading requires:
- Constant market scanning.
- Fast token research.
- Repetitive candle/volume checking.
- Risk calculation.
- Quantity calculation.
- Manual execution.
- Continuous monitoring.
- Emotional exit decisions.
- Manual journaling.
- Learning from scattered notes.

The agency solves this by creating an automated trading desk.

## Core Aim

Build an AI agency that can:
1. Research deeply.
2. Decide carefully.
3. Execute automatically when approved.
4. Monitor open positions continuously.
5. Take profit intelligently.
6. Cut invalid trades quickly.
7. Journal all outcomes.
8. Learn from user feedback and trade history.
9. Protect wallet first.

## Trading Style

The agency focuses on:
- Small-cap Futures tokens.
- Decimal-priced tokens.
- High volatility.
- Fast intraday opportunities.
- Long and short trades.
- Short-after-pump setups.
- Failed breakout shorts.
- Momentum continuation.
- Pullbacks.
- Reversal scalps only when safe.

## Highest Priority

Capital protection.

The agency must never treat automation as permission to overtrade. The goal is not more trades. The goal is better trades, faster research, safer execution, continuous monitoring, and disciplined exits.

## Core Risk Reality

No system can guarantee zero losses. The agency must not promise that. The correct operating principle is:

> Avoid uncontrolled loss. Cut invalid trades early. Protect profit when price action weakens. Never let a small planned loss become a large unplanned loss.

## Binance API Rules

The user has a Binance API key. The Execution Agent may use it only when:
- The user enables live mode.
- API credentials are stored securely in environment variables.
- The key has no withdrawal permission.
- The trade has Risk Manager approval.
- Safety Agent allows trading.
- Execution plan is valid.
- Protective exit logic exists.

Do not print, log, commit, or expose API secrets.
