# Telegram announcements

When an editor publishes a post, the app can post an announcement (title, excerpt, link) to a Telegram channel. This is optional and off by default.

## How it works

- `blog/services/telegram.py` — `send_new_post_announcement(post, absolute_url)` sends the message via [`python-telegram-bot`](https://docs.python-telegram-bot.org/) (`requirements.txt`).
- `blog/views/posts.py` — `post_publish` calls it right after marking the post published, passing `request.build_absolute_uri(post.get_absolute_url())` as the link.
- Config comes from `settings.TELEGRAM_BOT_TOKEN` / `settings.TELEGRAM_CHANNEL_ID`, read via `python-decouple` in `config/settings.py`.

If either setting is empty, `send_new_post_announcement` returns immediately — no import error, no network call. If Telegram's API call fails (bad token, network issue, bot removed from channel, etc.), the error is logged to the `blog` logger and swallowed — **publishing a post never fails because of Telegram**, by design.

The library's `Bot.send_message` is async-only (`python-telegram-bot` v20+), so the service wraps the call in `asyncio.run(...)` to call it from a normal sync Django view.

## Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram, run `/newbot`, and copy the token it gives you (looks like `123456789:AAF...`).
2. Add the bot as an **admin** of the target channel (Channel → Administrators → Add Admin). Without admin rights the bot can't post.
3. Get the channel identifier — either its public `@username` (if it has one) or its numeric chat ID (if private; e.g. via a bot like `@userinfobot` or the `getUpdates` API).
4. Set both values in your local `.env` (never in `.env.example` — that file is committed and must stay blank):

   ```
   TELEGRAM_BOT_TOKEN=123456789:AAF...
   TELEGRAM_CHANNEL_ID=@yourchannel
   ```
5. Restart the dev server. Publish a post to confirm the announcement lands in the channel.

## Disabling

Leave `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHANNEL_ID` unset (the default) — publishing works exactly as before, with no Telegram calls made.

## Notes / limitations

- One-way only: this sends announcements out, it does not run a bot that listens for commands/updates (no polling, no webhook).
- Only wired into `post_publish`. `post_approve` and other status transitions do not announce.
- If a channel/token is misconfigured, the failure only shows up in the `blog` logger — there's no UI feedback to the publishing editor.
