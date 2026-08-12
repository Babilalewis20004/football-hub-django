import asyncio
import logging

from django.conf import settings
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger("blog")


def send_new_post_announcement(post, absolute_url):
    """Post a "new article" announcement to the configured Telegram channel.

    Best-effort: disabled when no token/channel is configured, and any
    Telegram-side failure is logged rather than raised, so a bot outage
    can never block an editor from publishing a post. Returns True only
    when the message actually sent, so callers can record that fact.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    channel_id = settings.TELEGRAM_CHANNEL_ID

    if not token or not channel_id:
        return False

    text = f"🆕 {post.title}\n\n{post.excerpt}\n\n{absolute_url}"

    try:
        asyncio.run(_send_message(token, channel_id, text))
        return True
    except TelegramError:
        logger.exception(f"Failed to send Telegram announcement for post: {post.title}")
        return False


async def _send_message(token, channel_id, text):
    async with Bot(token=token) as bot:
        await bot.send_message(chat_id=channel_id, text=text)
