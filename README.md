# VIP Payment Verification Bot

Telegram bot for manual payment verification before giving access to a VIP channel.

## Flow

1. User opens /start.
2. Bot shows bank payment details.
3. User pays and sends a screenshot.
4. Admin receives the screenshot.
5. Admin approves or rejects it.
6. After approval, user uses /join.
7. Bot creates a single-member invite link to the VIP channel.

## Required environment variables

- TELEGRAM_BOT_TOKEN
- ADMIN_ID
- VIP_CHANNEL_ID
- PAYMENT_NAME
- PAYMENT_NUMBER
- PAYMENT_AMOUNT

Optional:
- VIP_TITLE
- DB_PATH

## Telegram setup

1. Add the bot to your VIP channel as an administrator.
2. Give the bot permission to invite users.
3. Put the bot token and settings into your hosting platform's Environment Variables.
4. Never commit the real bot token or bank details to GitHub.

## Run locally

```bash
pip install -r requirements.txt
python bot.py
```

## Deploy

Use a Python worker/background service on your hosting provider.

Start command:

```bash
python bot.py
```

Build/install command:

```bash
pip install -r requirements.txt
```
