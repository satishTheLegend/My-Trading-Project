# Telegram Control Memory

## Remember

- User reporting preferences (concise vs detailed).
- Preferred summary length.
- Last Telegram command per chat.
- Last Telegram alert per chat.
- Pending approvals awaiting user decision.
- Authorized chat IDs.
- Unauthorized access attempts (count, last seen).
- User feedback from Telegram about message quality.

## Never store

- `TELEGRAM_BOT_TOKEN`.
- `BINANCE_API_KEY` or `BINANCE_API_SECRET`.
- Any private credential.

## Auto-learning

- Learn the user's preferred alert style.
- Learn which summaries actually get acted on.
- Learn whether the user prefers detailed or concise updates and adjust template choice accordingly.
