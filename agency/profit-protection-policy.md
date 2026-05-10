# Profit Protection Policy

The user wants every trade to be profit-seeking. The system **cannot guarantee** that — leveraged futures trading always has loss risk — but every trade must be actively managed to seek profit and avoid uncontrolled losses.

## Core Principle

> Every trade is profit-seeking, fee-aware, risk-limited, actively monitored, exited when invalid, and journaled after closure. Never let a planned small loss become an uncontrolled large loss.

## Hard No-Go Rules

The agency must **never**:

- Hold a losing trade indefinitely.
- Remove the stop-loss to avoid realising loss.
- Average down automatically.
- Increase leverage to recover a loss.
- Hide losing trades from journals or Telegram.
- Mark a losing position as "pending profit" or "hold for recovery".
- Wait for profit when liquidation risk is increasing.
- Disable safety caps because the model "feels confident".

## Profit Protection Rules (in profit)

When unrealized PnL > 0:

- Track maximum favorable PnL (MFE).
- At first take-profit target → consider partial exit (default 50%).
- After first TP → raise stop to breakeven.
- If profit covers fees and price action weakens → reduce or close.
- If MFE pulls back ≥ N×ATR (default 1.2) → trail the stop tighter.
- If BTC/ETH moves strongly against the position → protect profit early.
- If volume fades after a move → reduce or close.
- On candle reversal at a key level → alert Exit Agent.

These rules are encoded in `scripts/exit_simulator.py` and `scripts/profit_protection.py`.

## Loss Control Rules (in loss)

When unrealized PnL ≤ 0:

- Re-check whether the original setup is still valid.
- If invalidation hits → exit at market (reduce-only).
- If liquidation distance becomes unsafe → exit.
- If stop / protection went missing → emergency exit through the Safety Agent.
- If loss reaches the planned max-loss budget → exit (it's no longer a "small planned loss").
- Never widen the stop without explicit Risk Manager approval.

## Manual Position Handling

For positions opened manually on Binance:

- Monitor and report.
- Recommend profit-taking or risk-reduction actions to the user.
- Auto-close only if `ALLOW_AUTO_CLOSE_MANUAL_POSITIONS=true` or the Safety Agent declares emergency.

## Honest Journaling

Every trade — winning or losing — is journaled with:

- Net PnL (signed; losses are negative).
- Fees + funding paid.
- Reason for exit.
- Mistake tags.
- Lessons.

Hiding a loss from the journal would corrupt the Learning Agent's evidence and is never permitted.
