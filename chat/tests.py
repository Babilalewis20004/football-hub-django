import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import ChatMessage, ChatSession

User = get_user_model()


def _login_and_verify(client, username, password, device):
    """
    Logs a test client in and marks its session as having passed OTP
    verification (the way django_otp.login() would after a real verify).
    Needed because 'editor'/'admin' roles are gated by
    TwoFactorEnforcementMiddleware, which otherwise redirects every request
    to the 2FA setup/verify flow before it reaches the view under test.
    """
    client.login(username=username, password=password)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()


class ChatBaseTestCase(TestCase):

    def setUp(self):
        self.client = Client()

        self.visitor = User.objects.create_user(
            username="visitor",
            email="visitor@test.com",
            password="Password123!",
        )

        self.other_user = User.objects.create_user(
            username="other",
            email="other@test.com",
            password="Password123!",
        )

        self.agent = User.objects.create_user(
            username="agent",
            email="agent@test.com",
            password="Password123!",
            role="editor",
        )
        self.agent_device = TOTPDevice.objects.create(
            user=self.agent, name="test-device", confirmed=True
        )


class StartChatViewTests(ChatBaseTestCase):

    def test_get_not_allowed(self):
        response = self.client.get(reverse("chat_start"))
        self.assertEqual(response.status_code, 405)

    def test_anonymous_start_creates_session_with_given_name(self):
        response = self.client.post(
            reverse("chat_start"),
            data=json.dumps({"name": "Football Fan"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["visitor_name"], "Football Fan")
        self.assertEqual(data["status"], "open")
        self.assertTrue(ChatSession.objects.filter(id=data["session_id"]).exists())

    def test_anonymous_start_defaults_name_to_visitor(self):
        response = self.client.post(reverse("chat_start"), data="{}", content_type="application/json")
        self.assertEqual(response.json()["visitor_name"], "Visitor")

    def test_malformed_json_body_falls_back_to_defaults(self):
        response = self.client.post(reverse("chat_start"), data="not-json", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["visitor_name"], "Visitor")

    def test_authenticated_start_uses_username(self):
        self.client.login(username="visitor", password="Password123!")
        response = self.client.post(reverse("chat_start"), data="{}", content_type="application/json")
        self.assertEqual(response.json()["visitor_name"], "visitor")
        session = ChatSession.objects.get(id=response.json()["session_id"])
        self.assertEqual(session.visitor, self.visitor)

    def test_reopening_start_reuses_existing_open_session(self):
        self.client.login(username="visitor", password="Password123!")
        first = self.client.post(reverse("chat_start"), data="{}", content_type="application/json").json()
        second = self.client.post(reverse("chat_start"), data="{}", content_type="application/json").json()

        self.assertEqual(first["session_id"], second["session_id"])
        self.assertEqual(ChatSession.objects.filter(visitor=self.visitor).count(), 1)


class ChatMessagesViewTests(ChatBaseTestCase):

    def setUp(self):
        super().setUp()
        self.session = ChatSession.objects.create(
            visitor=self.visitor,
            visitor_name="visitor",
            session_key="visitor-session-key",
        )
        ChatMessage.objects.create(
            session=self.session,
            sender=self.visitor,
            sender_name="visitor",
            body="Hello, need help",
        )

    def test_owner_can_view_messages(self):
        self.client.login(username="visitor", password="Password123!")
        response = self.client.get(
            reverse("chat_messages", kwargs={"session_id": self.session.id})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["message"], "Hello, need help")

    def test_support_agent_can_view_messages(self):
        _login_and_verify(self.client, "agent", "Password123!", self.agent_device)
        response = self.client.get(
            reverse("chat_messages", kwargs={"session_id": self.session.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_unrelated_user_forbidden(self):
        self.client.login(username="other", password="Password123!")
        response = self.client.get(
            reverse("chat_messages", kwargs={"session_id": self.session.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_with_matching_session_key_allowed(self):
        session = self.client.session
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        anon_session = ChatSession.objects.create(
            visitor_name="Anon Visitor",
            session_key=session.session_key,
        )
        response = self.client.get(
            reverse("chat_messages", kwargs={"session_id": anon_session.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_missing_session_404(self):
        response = self.client.get(reverse("chat_messages", kwargs={"session_id": 999999}))
        self.assertEqual(response.status_code, 404)


class CloseChatViewTests(ChatBaseTestCase):

    def setUp(self):
        super().setUp()
        self.session = ChatSession.objects.create(
            visitor=self.visitor,
            visitor_name="visitor",
            session_key="visitor-session-key",
        )

    def test_get_not_allowed(self):
        response = self.client.get(reverse("chat_close", kwargs={"session_id": self.session.id}))
        self.assertEqual(response.status_code, 405)

    def test_owner_can_close_session(self):
        self.client.login(username="visitor", password="Password123!")
        response = self.client.post(reverse("chat_close", kwargs={"session_id": self.session.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "closed")
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "closed")

    def test_unrelated_user_forbidden(self):
        self.client.login(username="other", password="Password123!")
        response = self.client.post(reverse("chat_close", kwargs={"session_id": self.session.id}))
        self.assertEqual(response.status_code, 403)

    def test_agent_can_close_session(self):
        _login_and_verify(self.client, "agent", "Password123!", self.agent_device)
        response = self.client.post(reverse("chat_close", kwargs={"session_id": self.session.id}))
        self.assertEqual(response.status_code, 200)


class SupportInboxViewTests(ChatBaseTestCase):

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("support_inbox"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_non_agent_forbidden(self):
        self.client.login(username="visitor", password="Password123!")
        response = self.client.get(reverse("support_inbox"))
        self.assertEqual(response.status_code, 403)

    def test_agent_can_view_inbox(self):
        _login_and_verify(self.client, "agent", "Password123!", self.agent_device)
        response = self.client.get(reverse("support_inbox"))
        self.assertEqual(response.status_code, 200)


class SupportChatRoomViewTests(ChatBaseTestCase):

    def setUp(self):
        super().setUp()
        self.session = ChatSession.objects.create(
            visitor=self.visitor,
            visitor_name="visitor",
            session_key="visitor-session-key",
        )
        ChatMessage.objects.create(
            session=self.session,
            sender=self.visitor,
            sender_name="visitor",
            body="Unread visitor message",
            is_staff_message=False,
            is_read=False,
        )

    def test_non_agent_forbidden(self):
        self.client.login(username="visitor", password="Password123!")
        response = self.client.get(
            reverse("support_chat_room", kwargs={"session_id": self.session.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_agent_can_view_room_and_messages_marked_read(self):
        _login_and_verify(self.client, "agent", "Password123!", self.agent_device)
        response = self.client.get(
            reverse("support_chat_room", kwargs={"session_id": self.session.id})
        )
        self.assertEqual(response.status_code, 200)
        message = ChatMessage.objects.get(session=self.session)
        self.assertTrue(message.is_read)

    def test_missing_session_404(self):
        _login_and_verify(self.client, "agent", "Password123!", self.agent_device)
        response = self.client.get(reverse("support_chat_room", kwargs={"session_id": 999999}))
        self.assertEqual(response.status_code, 404)
