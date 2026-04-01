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
Schedule/
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

- **Start application**: Runs `cd Schedule && python bot.py` — polling mode for Replit development

## Vercel Deployment Steps

1. Push the full repo to GitHub
2. Go to [vercel.com](https://vercel.com) → **New Project** → Import your repo
3. **Important**: In the project settings, set **Root Directory** to `Schedule`
4. Set the following Environment Variables in Vercel dashboard:
   - `TELEGRAM_BOT_TOKEN` — bot token from @BotFather
   - `ADMIN_ID` — your Telegram user ID (e.g. `123456789`)
   - `VERCEL` — set to `1` (enables `/tmp` as data directory)
5. Click **Deploy**
6. After deployment, register the webhook with Telegram (run once in your browser):
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://<your-vercel-domain>/api/webhook
   ```
7. Verify webhook is active:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo
   ```

## Environment Variables

| Variable            | Where        | Description                                      |
|---------------------|--------------|--------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`| Secret       | Bot token from @BotFather                        |
| `ADMIN_ID`          | Env var      | Telegram user ID of the admin                    |
| `VERCEL`            | Vercel only  | Set to `1` to use `/tmp` as data directory       |

## How It Works on Vercel

- **`/api/webhook`** — Telegram sends every update to this endpoint. The function processes the update and responds.
- **`/api/cron`** — Runs every minute (Vercel Cron). Checks `scheduled_messages.json` in `/tmp` and sends any due messages.

## Features

- Schedule messages to Telegram groups with a specific date/time
- Support for all message types: text, photo, video, document, sticker, voice, audio, animation, video_note, contact, location, venue, poll, dice, forward
- List and delete scheduled messages
- Automatic group tracking when bot is added
- Admin-only access
