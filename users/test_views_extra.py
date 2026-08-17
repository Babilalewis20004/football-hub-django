"""
Targeted tests filling gaps left by users/tests.py and users/test_two_factor.py:
the login view's `next`-redirect branches, the captcha-failure-that-also-locks
combination, profile updates, account deletion, the "already enrolled" setup
redirect, the OTP-device-throttled verify path, and the "2FA not enabled"
regenerate-codes guard.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import LoginAttempt
from .tests import WRONG_CAPTCHA, _solved_captcha
from .test_two_factor import _mark_session_verified, PASSWORD
from .twofactor import generate_recovery_codes, user_has_2fa_enabled

User = get_user_model()


class LoginNextRedirectTests(TestCase):

    def setUp(self):
        self.login_url = reverse("login")

    def test_next_redirects_directly_when_no_2fa_gate(self):
        User.objects.create_user(username="readeruser", password=PASSWORD, role="reader")
        next_url = reverse("dashboard")

        response = self.client.post(
            self.login_url,
            {
                "username": "readeruser",
                "password": PASSWORD,
                "role": "reader",
                "next": next_url,
                **_solved_captcha(),
            },
        )

        self.assertRedirects(response, next_url)

    def test_next_is_appended_to_two_factor_url_when_gated(self):
        User.objects.create_user(username="editoruser", password=PASSWORD, role="editor")
        next_url = reverse("dashboard")

        response = self.client.post(
            self.login_url,
            {
                "username": "editoruser",
                "password": PASSWORD,
                "role": "editor",
                "next": next_url,
                **_solved_captcha(),
            },
        )

        self.assertRedirects(response, f"{reverse('two_factor_setup')}?next={next_url}")


class LoginCaptchaAlsoLocksOutTests(TestCase):
    """
    Covers the case where a wrong CAPTCHA submission is itself the failure
    that crosses the lockout threshold, so the CAPTCHA-failure branch has to
    re-check lockout and surface it immediately (users.views.login_view,
    the block right after `record_attempt(..., reason="captcha_failed")`).
    """

    def setUp(self):
        self.username = "lockme"
        User.objects.create_user(username=self.username, password=PASSWORD, role="reader")
        self.login_url = reverse("login")

        # 4 prior failures: enough to require a CAPTCHA (threshold 2) and
        # one short of the lockout threshold (5), so the wrong-CAPTCHA
        # attempt below becomes the 5th failure and trips the lock.
        for _ in range(4):
            LoginAttempt.objects.create(username=self.username, successful=False)

    def test_wrong_captcha_that_trips_lockout_shows_lockout_message(self):
        response = self.client.post(
            self.login_url,
            {
                "username": self.username,
                "password": "wrong-password",
                "role": "reader",
                **WRONG_CAPTCHA,
            },
        )

        self.assertContains(response, "temporarily locked")
        self.assertTrue(
            LoginAttempt.objects.filter(
                username=self.username, reason="captcha_failed"
            ).exists()
        )


class ProfileUpdateViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="reader", password=PASSWORD, role="reader"
        )
        self.client.login(username="reader", password=PASSWORD)
        self.profile_url = reverse("profile")

    def test_valid_update_saves_and_redirects(self):
        response = self.client.post(
            self.profile_url,
            {"bio": "Lifelong Football Hub reader.", "favorite_team": "Arsenal"},
        )

        self.assertRedirects(response, self.profile_url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, "Lifelong Football Hub reader.")
        self.assertEqual(self.user.favorite_team, "Arsenal")

    def test_invalid_avatar_does_not_save_and_shows_form_errors(self):
        bogus_image = SimpleUploadedFile(
            "avatar.jpg", b"not-actually-an-image", content_type="image/jpeg"
        )

        response = self.client.post(
            self.profile_url,
            {"bio": "", "favorite_team": "", "avatar": bogus_image},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar.name, "avatars/default.jpg")


class DeleteAccountViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="reader", password=PASSWORD, role="reader"
        )
        self.client.login(username="reader", password=PASSWORD)
        self.delete_url = reverse("delete_account")

    def test_wrong_password_does_not_delete_account(self):
        response = self.client.post(self.delete_url, {"password": "wrong-password"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("delete_error", response.context)
        self.assertTrue(User.objects.filter(username="reader").exists())

    def test_correct_password_deletes_account_and_redirects_home(self):
        response = self.client.post(self.delete_url, {"password": PASSWORD})

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(User.objects.filter(username="reader").exists())


class TwoFactorSetupAlreadyEnabledTests(TestCase):

    def test_setup_redirects_to_profile_when_already_enabled(self):
        user = User.objects.create_user(username="reader", password=PASSWORD, role="reader")
        device = TOTPDevice.objects.create(user=user, confirmed=True)
        generate_recovery_codes(user)

        self.client.login(username="reader", password=PASSWORD)
        _mark_session_verified(self.client, device)

        response = self.client.get(reverse("two_factor_setup"))

        self.assertRedirects(response, reverse("profile"))


class TwoFactorVerifyWithoutDeviceTests(TestCase):

    def test_verify_redirects_to_setup_when_no_confirmed_device(self):
        User.objects.create_user(username="reader", password=PASSWORD, role="reader")
        self.client.login(username="reader", password=PASSWORD)

        response = self.client.get(reverse("two_factor_verify"))

        self.assertRedirects(response, reverse("two_factor_setup"))


class TwoFactorVerifyThrottledTests(TestCase):

    def test_throttled_device_shows_wait_message_instead_of_invalid_code(self):
        user = User.objects.create_user(username="authoruser", password=PASSWORD, role="author")
        device = TOTPDevice.objects.create(user=user, confirmed=True)
        # Simulate an already-in-progress throttle window rather than
        # brute-forcing real failed attempts through the view. A high
        # failure count pushes the required delay well past however long
        # this request (login + full page render) actually takes to run,
        # so the throttle window can't elapse out from under the test.
        device.throttling_failure_count = 10
        device.throttling_failure_timestamp = timezone.now()
        device.save()

        self.client.login(username="authoruser", password=PASSWORD)
        response = self.client.post(reverse("two_factor_verify"), {"code": "000000"})

        self.assertContains(response, "Too many incorrect attempts")
        self.assertNotContains(response, "Invalid code")


class TwoFactorRegenerateCodesNotEnabledTests(TestCase):

    def test_regenerate_without_2fa_enabled_shows_error(self):
        User.objects.create_user(username="reader", password=PASSWORD, role="reader")
        self.client.login(username="reader", password=PASSWORD)

        response = self.client.post(
            reverse("two_factor_regenerate_codes"), {"password": PASSWORD}
        )

        self.assertRedirects(response, reverse("profile"))
