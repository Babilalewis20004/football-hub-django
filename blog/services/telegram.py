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
    can never block an editor from publishing a post.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    channel_id = settings.TELEGRAM_CHANNEL_ID

    if not token or not channel_id:
        return

    text = f"🆕 {post.title}\n\n{post.excerpt}\n\n{absolute_url}"

    try:
        asyncio.run(_send_message(token, channel_id, text))
    except TelegramError:
        logger.exception(f"Failed to send Telegram announcement for post: {post.title}")


async def _send_message(token, channel_id, text):
    async with Bot(token=token) as bot:
        await bot.send_message(chat_id=channel_id, text=text)
