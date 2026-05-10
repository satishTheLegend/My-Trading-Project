# Telegram Control Policy

Telegram is the user-facing control + notification layer. Implementation lives in `scripts/telegram_bot.py` + friends.

## Environment Variables

Required:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional:
- `TELEGRAM_ALLOWED_CHAT_IDS` (comma-separated, additional allowed chats)
- `TELEGRAM_ENABLE_LONG_POLLING` (default true)
- `TELEGRAM_ENABLE_WEBHOOK` (default false)
- `TELEGRAM_WEBHOOK_URL`

## What Telegram Is For

1. Trade alerts (entry, stop/protection placement, TP hit, partial exit, full exit, emergency exit).
2. Manual-position-detected alerts.
3. Mode change + safety pause/resume notifications.
4. Daily summaries.
5. Command-based control (see below).
6. Free-form chat with the agency via `/ask`.
7. Optional confirmation prompt for live orders.

## Telegram Commands

Registered via `setMyCommands` (see `scripts/telegram_commands.py::TELEGRAM_COMMANDS`):

- `/start` — bot status and command list
- `/help` — explain commands
- `/status` — system mode, safety, wallet, open positions
- `/mode` — show current mode
- `/paper` — switch mode request to paper
- `/live` — request live-readiness check (NOT blind activation)
- `/scan` — run market scan
- `/positions` — show open and manual positions
- `/sync` — sync Binance account positions
- `/summary` — show latest trade/day summary
- `/pause` — pause new trades
- `/resume` — resume if safety allows
- `/close SYMBOL` — request reduce-only close for one position
- `/emergency` — trigger emergency shutdown
- `/risk` — show risk settings
- `/pnl` — show PnL summary
- `/journal` — latest journal entries
- `/ask MESSAGE` — ask Claude/system a question
- `/approve ID` — approve pending action (semi-auto queue)
- `/reject ID` — reject pending action
- `/settings` — show runtime config summary (NO secrets)

## Security

- Only chat IDs in `TELEGRAM_CHAT_ID` ∪ `TELEGRAM_ALLOWED_CHAT_IDS` may control the bot.
- Messages from unknown chats: log the unauthorized attempt to `data/telegram-events.jsonl`, optionally send a generic refusal, never reveal config.
- Never echo `TELEGRAM_BOT_TOKEN`, `BINANCE_API_KEY`, `BINANCE_API_SECRET`, or any other secret in any reply.
- Never execute live trades from free-form `/ask` text — only structured commands route to execution paths, and even those go through the same Risk + Safety + Execution chain as the CLI.

## Notification Triggers

The Telegram Notifier sends after each of:

- Workflow start
- Mode change
- Binance sync result
- Manual position detected
- Trade proposal created
- Risk approval / rejection
- Live order placed
- Entry filled
- Stop/protection placed
- TP hit / partial exit / full exit / emergency exit
- Trade closed (with the post-trade summary template)
- Daily summary
- Safety warning (pause / resume / breach)
- API failure
- Position mismatch

See `agency/telegram-templates.md` for the message templates.

## Resilience

- If Telegram is down, the cycle still runs (logs the failure).
- If `REQUIRE_TELEGRAM_CONFIRMATION_FOR_LIVE_ORDER=true` and Telegram is unavailable → live execution is blocked (cycle falls back to live-readiness only).
- Long polling vs webhook is selected from env. Long polling is the default for local dev; webhook needs a public HTTPS URL.
