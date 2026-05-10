---
description: Setup and verify Telegram bot integration for alerts and chat control.
---

Use the Telegram Control Agent.

Check:

- `TELEGRAM_BOT_TOKEN` exists in env (presence only — never echo)
- `TELEGRAM_CHAT_ID` exists in env
- `TELEGRAM_ALLOWED_CHAT_IDS` parsed
- Can call `getMe` against Telegram Bot API
- Can send a test message to the primary chat
- Can register commands with `setMyCommands` (using the list in `scripts/telegram_commands.py`)
- Can receive updates via long polling (`getUpdates`) or webhook (`setWebhook`)

Never print the token in the response.

Return:

```json
{
  "telegram_ready": false,
  "send_test_status": "",
  "commands_registered": false,
  "authorized_chat_ids": [],
  "warnings": []
}
```
