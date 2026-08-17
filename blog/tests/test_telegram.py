from unittest.mock import AsyncMock, patch

from django.test import TestCase, override_settings

from telegram.error import TelegramError

from blog.services.telegram import send_new_post_announcement


class _FakePost:
    title = "City Win Again"
    excerpt = "A short match report."


@override_settings(TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_CHANNEL_ID="123")
class SendNewPostAnnouncementTests(TestCase):

    def test_returns_false_when_not_configured(self):
        with override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID=""):
            result = send_new_post_announcement(_FakePost(), "https://example.com/post/city-win-again/")
        self.assertFalse(result)

    def test_returns_false_when_only_token_missing(self):
        with override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="123"):
            result = send_new_post_announcement(_FakePost(), "https://example.com/post/city-win-again/")
        self.assertFalse(result)

    # Mocking `_send_message` itself (rather than `asyncio.run`) lets the
    # real asyncio.run() actually await the mocked coroutine, so no
    # coroutine object is ever left dangling/un-awaited between tests.
    @patch("blog.services.telegram._send_message", new_callable=AsyncMock)
    def test_returns_true_on_success(self, mock_send_message):
        result = send_new_post_announcement(_FakePost(), "https://example.com/post/city-win-again/")
        self.assertTrue(result)
        mock_send_message.assert_called_once()

    @patch("blog.services.telegram._send_message", new_callable=AsyncMock, side_effect=TelegramError("boom"))
    def test_telegram_error_is_caught_and_returns_false(self, mock_send_message):
        result = send_new_post_announcement(_FakePost(), "https://example.com/post/city-win-again/")
        self.assertFalse(result)
