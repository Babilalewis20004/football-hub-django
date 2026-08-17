from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from .models import Feedback, Subscriber

User = get_user_model()


class StaticPageViewTests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_static_pages_return_200(self):
        urls = [
            "privacy_policy",
            "terms_of_use",
            "about_us",
            "cookies",
            "careers",
            "contact_us",
        ]
        for name in urls:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)


class FeedbackViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="reader",
            email="reader@test.com",
            password="Password123!",
        )

    def test_get_renders_empty_form(self):
        response = self.client.get(reverse("feedback"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_anonymous_valid_submission_creates_feedback(self):
        response = self.client.post(
            reverse("feedback"),
            {
                "rating": 5,
                "name": "Jane Doe",
                "email": "jane@example.com",
                "comment": "Loved the coverage!",
            },
        )
        self.assertRedirects(response, reverse("feedback"))
        self.assertTrue(
            Feedback.objects.filter(email="jane@example.com", rating=5).exists()
        )
        feedback = Feedback.objects.get(email="jane@example.com")
        self.assertIsNone(feedback.user)

    def test_authenticated_submission_fills_in_user_defaults(self):
        self.client.login(username="reader", password="Password123!")
        response = self.client.post(
            reverse("feedback"),
            {
                "rating": 4,
                "name": "",
                "email": "",
                "comment": "Pretty good site.",
            },
        )
        self.assertRedirects(response, reverse("feedback"))
        feedback = Feedback.objects.get(comment="Pretty good site.")
        self.assertEqual(feedback.user, self.user)
        self.assertEqual(feedback.name, self.user.username)
        self.assertEqual(feedback.email, self.user.email)

    def test_invalid_submission_does_not_create_feedback(self):
        response = self.client.post(reverse("feedback"), {"rating": "", "comment": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Feedback.objects.exists())


class SubscribeViewTests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_get_not_allowed(self):
        response = self.client.get(reverse("subscribe"))
        self.assertEqual(response.status_code, 405)

    def test_valid_email_creates_subscriber_and_redirects_home(self):
        response = self.client.post(reverse("subscribe"), {"email": "fan@example.com"})
        self.assertRedirects(response, reverse("home"))
        self.assertTrue(Subscriber.objects.filter(email="fan@example.com").exists())

    def test_duplicate_email_does_not_create_second_subscriber(self):
        Subscriber.objects.create(email="fan@example.com")
        self.client.post(reverse("subscribe"), {"email": "fan@example.com"})
        self.assertEqual(Subscriber.objects.filter(email="fan@example.com").count(), 1)

    def test_invalid_email_redirects_home_without_creating(self):
        response = self.client.post(reverse("subscribe"), {"email": "not-an-email"})
        self.assertRedirects(response, reverse("home"))
        self.assertFalse(Subscriber.objects.exists())

    def test_next_param_redirects_to_safe_url(self):
        response = self.client.post(
            reverse("subscribe"),
            {"email": "fan2@example.com", "next": reverse("about_us")},
        )
        self.assertRedirects(response, reverse("about_us"))

    def test_next_param_ignores_unsafe_external_url(self):
        response = self.client.post(
            reverse("subscribe"),
            {"email": "fan3@example.com", "next": "https://evil.example.com/"},
        )
        self.assertRedirects(response, reverse("home"))
