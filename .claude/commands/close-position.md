---
description: Request safe reduce-only close for a specific symbol.
---

Arguments:
`$ARGUMENTS`   (e.g. `DOGEUSDT`)

Routes through:

1. Binance Sync Agent — confirm position exists.
2. Position Manager Agent — load local state.
3. Risk Manager Agent — sanity check the close (size, current PnL).
4. Exit Agent — decide partial vs full close.
5. Execution Agent — fire `reduceOnly=true` market order.
6. Journal Agent — record the close.
7. Telegram Control Agent — send the Trade Closed template.

If the symbol has no open position (neither agency nor manual), the response says so clearly without firing any order.
