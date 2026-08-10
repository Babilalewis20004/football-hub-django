from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from captcha.models import CaptchaStore

from .middleware import SESSION_INACTIVITY_TIMEOUT, SESSION_TIMEOUT_MESSAGE
from .models import LoginAttempt
from .security import MAX_FAILED_ATTEMPTS, LOCKOUT_DURATION, CAPTCHA_AFTER_ATTEMPTS

User = get_user_model()


def _solved_captcha():
    """
    POST data for a CAPTCHA that will validate correctly. Creates a real
    CaptchaStore row (bypassing only the rendered image, not the actual
    challenge/response check), so this exercises the same validation path
    a real solved CAPTCHA would - unlike CAPTCHA_TEST_MODE, which
    django-simple-captcha snapshots at import time and can't be toggled
    per-test via override_settings.

    A fresh store is required per call: a successful *or* failed lookup
    deletes the store, so it can only be spent once.
    """
    store = CaptchaStore.objects.create(challenge="captcha-test", response="captcha-test")
    return {"captcha_0": store.hashkey, "captcha_1": store.response}


WRONG_CAPTCHA = {"captcha_0": "no-such-hashkey", "captcha_1": "wrong-answer"}


class LoginLockoutTests(TestCase):
    def setUp(self):
        self.username = "testuser"
        self.password = "correct-horse-battery-staple"
        self.role = "reader"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            role=self.role,
        )
        self.login_url = reverse("login")

    def _post_login(self, username, password, role="reader", solve_captcha=True):
        # A real client always fills in the CAPTCHA once the page renders
        # one; sending a solved response on every request is harmless when
        # the view didn't require one (the extra fields are simply unused).
        data = {"username": username, "password": password, "role": role}
        if solve_captcha:
            data.update(_solved_captcha())
        return self.client.post(self.login_url, data)

    def test_successful_login(self):
        response = self._post_login(self.username, self.password, self.role)
        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(
            LoginAttempt.objects.filter(username=self.username, successful=True).exists()
        )

    def test_wrong_password_shows_generic_error(self):
        response = self._post_login(self.username, "wrong-password", self.role)
        self.assertContains(response, "Invalid credentials")
        self.assertEqual(
            LoginAttempt.objects.filter(
                username=self.username, successful=False, reason="invalid_credentials"
            ).count(),
            1,
        )

    def test_account_locks_after_max_failed_attempts(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            response = self._post_login(self.username, "wrong-password", self.role)

        self.assertContains(response, "temporarily locked")

        # Correct credentials must still be rejected while locked.
        response = self._post_login(self.username, self.password, self.role)
        self.assertContains(response, "temporarily locked")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_lockout_recorded_for_auditing(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._post_login(self.username, "wrong-password", self.role)
        self._post_login(self.username, self.password, self.role)

        self.assertTrue(
            LoginAttempt.objects.filter(username=self.username, reason="locked_out").exists()
        )

    def test_successful_login_resets_failed_counter(self):
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            self._post_login(self.username, "wrong-password", self.role)

        # One more failure would normally trip the lock, but a success
        # comes first and should reset the streak.
        self._post_login(self.username, self.password, self.role)
        self.client.logout()

        response = self._post_login(self.username, "wrong-password", self.role)
        self.assertContains(response, "Invalid credentials")
        self.assertNotContains(response, "temporarily locked")

    def test_lockout_expires_after_window(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._post_login(self.username, "wrong-password", self.role)

        # Fast-forward every recorded attempt to just past the lockout window.
        past = timezone.now() - LOCKOUT_DURATION - timedelta(seconds=1)
        LoginAttempt.objects.filter(username=self.username).update(timestamp=past)

        response = self._post_login(self.username, self.password, self.role)
        self.assertRedirects(response, reverse("dashboard"))

    def test_nonexistent_username_locks_out_identically(self):
        """
        A username with no matching account must produce the exact same
        lockout response as a real one, so the lockout message can't be
        used to enumerate valid accounts.
        """
        fake_response = None
        for _ in range(MAX_FAILED_ATTEMPTS):
            fake_response = self._post_login("no-such-user", "whatever", "reader")

        real_response = None
        for _ in range(MAX_FAILED_ATTEMPTS):
            real_response = self._post_login(self.username, "wrong-password", self.role)

        self.assertContains(fake_response, "temporarily locked")
        self.assertEqual(fake_response.context["error"], real_response.context["error"])

    def test_invalid_role_counts_toward_lockout(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            response = self._post_login(self.username, self.password, role="not-a-role")

        self.assertContains(response, "temporarily locked")


class LoginCaptchaTests(TestCase):
    """
    Progressive CAPTCHA gating on the public login form (users.security.
    requires_captcha), independent of the tests in LoginLockoutTests
    (which always submit a solved CAPTCHA and so never exercise this path).
    """

    def setUp(self):
        self.username = "captchauser"
        self.password = "correct-horse-battery-staple"
        self.role = "reader"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            role=self.role,
        )
        self.login_url = reverse("login")

    def _post_login(self, password, extra=None, role="reader"):
        data = {"username": self.username, "password": password, "role": role}
        if extra:
            data.update(extra)
        return self.client.post(self.login_url, data)

    def _fail_until_captcha_required(self):
        response = None
        for _ in range(CAPTCHA_AFTER_ATTEMPTS):
            response = self._post_login("wrong-password")
        return response

    def test_captcha_not_required_before_threshold(self):
        response = self._post_login("wrong-password")
        self.assertIsNone(response.context.get("captcha_form"))

    def test_captcha_required_after_threshold(self):
        response = self._fail_until_captcha_required()
        self.assertIsNotNone(response.context.get("captcha_form"))

    def test_login_blocked_without_captcha_once_required(self):
        self._fail_until_captcha_required()

        # Correct credentials, but no CAPTCHA response at all.
        response = self._post_login(self.password)
        self.assertContains(response, "CAPTCHA")
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertTrue(
            LoginAttempt.objects.filter(
                username=self.username, successful=False, reason="captcha_failed"
            ).exists()
        )

    def test_login_blocked_with_wrong_captcha(self):
        self._fail_until_captcha_required()

        response = self._post_login(self.password, extra=WRONG_CAPTCHA)
        self.assertContains(response, "CAPTCHA")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_succeeds_with_solved_captcha(self):
        self._fail_until_captcha_required()

        response = self._post_login(self.password, extra=_solved_captcha())
        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(
            LoginAttempt.objects.filter(username=self.username, successful=True).exists()
        )

    def test_captcha_required_before_account_locks_out(self):
        # The threshold must trip strictly before the lockout does, so
        # there's a chance to prove humanity before being locked out.
        self.assertLess(CAPTCHA_AFTER_ATTEMPTS, MAX_FAILED_ATTEMPTS)


class AdminLoginLockoutTests(TestCase):
    def setUp(self):
        self.username = "staffuser"
        self.password = "correct-horse-battery-staple"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            role="admin",
            is_staff=True,
        )
        self.admin_login_url = reverse("admin:login")

    def _post_admin_login(self, username, password, solve_captcha=True):
        data = {"username": username, "password": password, "next": "/admin/"}
        if solve_captcha:
            data.update(_solved_captcha())
        return self.client.post(self.admin_login_url, data)

    def test_successful_admin_login(self):
        response = self._post_admin_login(self.username, self.password)
        self.assertRedirects(response, "/admin/")
        self.assertTrue(
            LoginAttempt.objects.filter(username=self.username, successful=True).exists()
        )

    def test_wrong_password_shows_generic_django_error(self):
        response = self._post_admin_login(self.username, "wrong-password")
        self.assertNotContains(response, "temporarily locked")
        self.assertEqual(
            LoginAttempt.objects.filter(
                username=self.username, successful=False, reason="admin_invalid_login"
            ).count(),
            1,
        )

    def test_admin_account_locks_after_max_failed_attempts(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            response = self._post_admin_login(self.username, "wrong-password")

        self.assertContains(response, "temporarily locked")

        # Correct credentials must still be rejected while locked.
        response = self._post_admin_login(self.username, self.password)
        self.assertContains(response, "temporarily locked")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_admin_lockout_recorded_for_auditing(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._post_admin_login(self.username, "wrong-password")
        self._post_admin_login(self.username, self.password)

        self.assertTrue(
            LoginAttempt.objects.filter(
                username=self.username, reason="admin_locked_out"
            ).exists()
        )

    def test_admin_lockout_expires_after_window(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self._post_admin_login(self.username, "wrong-password")

        past = timezone.now() - LOCKOUT_DURATION - timedelta(seconds=1)
        LoginAttempt.objects.filter(username=self.username).update(timestamp=past)

        response = self._post_admin_login(self.username, self.password)
        self.assertRedirects(response, "/admin/")

    def test_lockout_is_shared_between_public_login_and_admin_login(self):
        """
        Failures against the same username via the public /login/ form must
        count toward the same lockout enforced on /admin/, so an attacker
        can't dodge the lock by switching surfaces.
        """
        login_url = reverse("login")

        for _ in range(MAX_FAILED_ATTEMPTS):
            self.client.post(
                login_url,
                {
                    "username": self.username,
                    "password": "wrong-password",
                    "role": "reader",
                    **_solved_captcha(),
                },
            )

        response = self._post_admin_login(self.username, self.password)
        self.assertContains(response, "temporarily locked")


class AdminLoginCaptchaTests(TestCase):
    """
    Progressive CAPTCHA gating on the admin login form
    (LockoutAwareAdminAuthenticationForm), mirroring LoginCaptchaTests.

    Unlike the public login view - which re-checks requires_captcha() right
    after recording a failure, so it can show the field on the very
    response that just tripped the threshold - the admin form only knows
    whether to add the `captcha` field when it's constructed, before that
    request's own outcome is recorded. So the field shows up one request
    later here than on the public form; _fail_until_captcha_required loops
    until it actually appears rather than assuming a fixed count.
    """

    def setUp(self):
        self.username = "captchastaff"
        self.password = "correct-horse-battery-staple"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            role="admin",
            is_staff=True,
        )
        self.admin_login_url = reverse("admin:login")

    def _post_admin_login(self, password, extra=None):
        data = {"username": self.username, "password": password, "next": "/admin/"}
        if extra:
            data.update(extra)
        return self.client.post(self.admin_login_url, data)

    def _fail_until_captcha_required(self):
        response = None
        for _ in range(MAX_FAILED_ATTEMPTS):
            response = self._post_admin_login("wrong-password")
            if b'name="captcha_0"' in response.content:
                break
        return response

    def test_captcha_field_rendered_after_threshold(self):
        response = self._fail_until_captcha_required()
        self.assertContains(response, 'name="captcha_0"')

    def test_admin_login_blocked_without_captcha_once_required(self):
        self._fail_until_captcha_required()

        response = self._post_admin_login(self.password)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertTrue(
            LoginAttempt.objects.filter(
                username=self.username, successful=False, reason="admin_captcha_failed"
            ).exists()
        )

    def test_admin_login_succeeds_with_solved_captcha(self):
        self._fail_until_captcha_required()

        response = self._post_admin_login(self.password, extra=_solved_captcha())
        self.assertRedirects(response, "/admin/")
        self.assertTrue(
            LoginAttempt.objects.filter(username=self.username, successful=True).exists()
        )


class SessionInactivityTimeoutTests(TestCase):
    def setUp(self):
        self.username = "idleuser"
        self.password = "correct-horse-battery-staple"
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            role="reader",
        )
        self.client.login(username=self.username, password=self.password)
        self.profile_url = reverse("profile")
        self.login_url = reverse("login")

    def _backdate_last_activity(self, seconds_ago):
        session = self.client.session
        session["last_activity"] = timezone.now().timestamp() - seconds_ago
        session.save()

    def test_authenticated_request_within_window_stays_logged_in(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_activity_inside_window_refreshes_timeout(self):
        self._backdate_last_activity(SESSION_INACTIVITY_TIMEOUT - 30)
        response = self.client.get(self.profile_url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_session_expires_after_inactivity_window(self):
        self._backdate_last_activity(SESSION_INACTIVITY_TIMEOUT + 1)

        response = self.client.get(self.profile_url)
        self.assertRedirects(response, f"{self.login_url}?next={self.profile_url}")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_expired_session_shows_timeout_message_on_login_page(self):
        self._backdate_last_activity(SESSION_INACTIVITY_TIMEOUT + 1)

        response = self.client.get(self.profile_url, follow=True)
        self.assertContains(response, SESSION_TIMEOUT_MESSAGE)

    def test_expired_session_cannot_reach_protected_view(self):
        self._backdate_last_activity(SESSION_INACTIVITY_TIMEOUT + 1)

        response = self.client.get(self.profile_url, follow=True)
        self.assertTemplateUsed(response, "users/login.html")


class RegisterCaptchaTests(TestCase):
    """CAPTCHA is required on every registration, not just progressively."""

    def setUp(self):
        self.register_url = reverse("register")

    def _post_register(self, extra=None):
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password1": "correct-horse-battery-staple",
            "password2": "correct-horse-battery-staple",
        }
        if extra:
            data.update(extra)
        return self.client.post(self.register_url, data)

    def test_registration_fails_without_captcha(self):
        response = self._post_register()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_registration_fails_with_wrong_captcha(self):
        response = self._post_register(extra=WRONG_CAPTCHA)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_registration_succeeds_with_solved_captcha(self):
        response = self._post_register(extra=_solved_captcha())
        self.assertRedirects(response, "/")
        self.assertTrue(User.objects.filter(username="newuser").exists())
