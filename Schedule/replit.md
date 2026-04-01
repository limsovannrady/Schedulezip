# Telegram Scheduler Bot

## Overview

A Telegram bot for scheduling and sending messages to groups, built in Khmer language. Supports webhook deployment on Vercel and polling mode on Replit.

## Stack

- **Language**: Python 3.11
- **Bot Framework**: python-telegram-bot >= 22.7 (with job-queue)
- **Package Manager**: uv
- **Deployment**: Vercel (webhook) / Replit (polling)

## Structure

```text
/
├── bot.py              # Entry point for Replit polling mode
├── bot_core.py         # All bot logic, handlers, and build_application()
├── api/
│   ├── webhook.py      # Vercel serverless function — handles Telegram updates
│   └── cron.py         # Vercel cron function — checks and sends scheduled messages
├── vercel.json         # Vercel config (routes + cron every minute)
├── requirements.txt    # Python dependencies
└── pyproject.toml      # Python project config
```

## Data Files (auto-generated, git-ignored)

- `groups.json` — tracked Telegram groups
- `user_groups.json` — user-to-group mapping
- `pending_schedules.json` — in-progress scheduling sessions
- `scheduled_messages.json` — queued scheduled messages

> **Note**: On Vercel, data files are stored in `/tmp` (ephemeral per function call). For production persistence, replace JSON file storage with a database (e.g., Vercel KV, Supabase, or PostgreSQL).

## Workflows

- **Telegram Bot**: Runs `python3 bot.py` — polling mode for local/Replit development

## Vercel Deployment Steps

1. Push code to GitHub
2. Import repo in Vercel dashboard
3. Set environment variables:
   - `TELEGRAM_BOT_TOKEN` — bot token from @BotFather
   - `ADMIN_ID` — your Telegram user ID
   - `VERCEL=1` — enables `/tmp` data directory
4. After deployment, set the webhook:
   ```
   https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<your-domain>/api/webhook
   ```

## Environment Variables

- `TELEGRAM_BOT_TOKEN` (secret): The bot token from @BotFather
- `ADMIN_ID` (optional): Telegram user ID of the admin (default: 5002402843)
- `VERCEL` (Vercel only): Set to `1` to use `/tmp` as data directory

## Features

- Schedule messages to Telegram groups with a specific date/time
- Support for all message types: text, photo, video, document, sticker, voice, audio, animation, video_note, contact, location, venue, poll, dice, forward
- List and delete scheduled messages
- Automatic group tracking when bot is added
- Admin-only access
