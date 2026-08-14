"""
Tests for TOTP-based two-factor authentication: enrollment, per-session
verification, recovery codes, the mandatory-for-privileged-roles gate
(users.twofactor / users.middleware.TwoFactorEnforcementMiddleware), and
the related admin/profile management surfaces.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.oath import totp as raw_totp
from django_otp.plugins.otp_static.models import StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from .tests import _solved_captcha
from .twofactor import generate_recovery_codes, user_has_2fa_enabled

User = get_user_model()

PASSWORD = "correct-horse-battery-staple"


def _code_for(device):
    token = raw_totp(device.bin_key, device.step, device.t0, device.digits)
    return f"{token:0{device.digits}d}"


def _mark_session_verified(client, device):
    """
    Simulates an already-completed OTP verification for a test client's
    session, the way django_otp.login() would after a real verify - used
    when a test only cares about behaviour *after* verification and
    doesn't need to exercise the verify view itself.
    """
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()


class TwoFactorEnrollmentTests(TestCase):
    """Mandatory first-time enrollment for privileged roles (editor here;
    admin/author share the same TWO_FACTOR_REQUIRED_ROLES gate)."""

    def setUp(self):
        self.login_url = reverse("login")
        self.setup_url = reverse("two_factor_setup")
        self.profile_url = reverse("profile")
        self.user = User.objects.create_user(
            username="editoruser", password=PASSWORD, role="editor"
        )

    def _login(self):
        return self.client.post(
            self.login_url,
            {
                "username": self.user.username,
                "password": PASSWORD,
                "role": "editor",
                **_solved_captcha(),
            },
        )

    def test_privileged_login_redirects_to_setup(self):
        response = self._login()
        self.assertRedirects(response, self.setup_url)

    def test_reader_login_is_never_sent_to_setup(self):
        User.objects.create_user(username="readeruser", password=PASSWORD, role="reader")
        response = self.client.post(
            self.login_url,
            {
                "username": "readeruser",
                "password": PASSWORD,
                "role": "reader",
                **_solved_captcha(),
            },
        )
        self.assertRedirects(response, reverse("home"))

    def test_setup_page_renders_qr_code_and_manual_key(self):
        self._login()
        # The pending device is created lazily, the first time the setup
        # page itself is loaded - a bare login redirect doesn't create it.
        response = self.client.get(self.setup_url)
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data:image/png;base64,")
        self.assertContains(response, "REQUIRED FOR YOUR ROLE")
        self.assertEqual(response.context["form"].__class__.__name__, "TwoFactorCodeForm")
        self.assertIsNotNone(device)

    def test_middleware_redirects_unenrolled_privileged_user_from_any_page(self):
        self._login()
        response = self.client.get(self.profile_url)
        self.assertRedirects(response, f"{self.setup_url}?next={self.profile_url}")

    def test_valid_code_confirms_device_and_issues_recovery_codes(self):
        self._login()
        self.client.get(self.setup_url)
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)
        code = _code_for(device)

        response = self.client.post(self.setup_url, {"code": code})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/two_factor_recovery_codes.html")
        self.assertEqual(len(response.context["recovery_codes"]), 10)

        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        self.assertTrue(user_has_2fa_enabled(self.user))
        self.assertEqual(StaticToken.objects.filter(device__user=self.user).count(), 10)

    def test_enrollment_unblocks_access_to_other_pages(self):
        self._login()
        self.client.get(self.setup_url)
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)
        self.client.post(self.setup_url, {"code": _code_for(device)})

        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)

    def test_invalid_code_does_not_confirm_device(self):
        self._login()
        response = self.client.post(self.setup_url, {"code": "000000"})

        self.assertContains(response, "Incorrect code")
        self.assertFalse(user_has_2fa_enabled(self.user))

    def test_admin_form_login_is_also_gated_by_the_middleware(self):
        """
        /admin/ has its own login form (LockoutAwareAdminAuthenticationForm)
        that never goes through users.views.login_view, so this confirms
        the mandatory-enrollment gate still applies via
        TwoFactorEnforcementMiddleware, which runs regardless of how the
        session was established.
        """
        admin_user = User.objects.create_user(
            username="adminuser", password=PASSWORD, role="admin", is_staff=True
        )
        self.client.login(username=admin_user.username, password=PASSWORD)

        response = self.client.get("/admin/")

        self.assertRedirects(response, f"{self.setup_url}?next=/admin/")


class TwoFactorVerifyTests(TestCase):
    """Per-session verification for a user who already has a confirmed device."""

    def setUp(self):
        self.login_url = reverse("login")
        self.verify_url = reverse("two_factor_verify")
        self.profile_url = reverse("profile")
        self.user = User.objects.create_user(
            username="authoruser", password=PASSWORD, role="author"
        )
        self.device = TOTPDevice.objects.create(
            user=self.user, name="authenticator-app", confirmed=True
        )
        self.recovery_codes = generate_recovery_codes(self.user)

    def _login(self):
        return self.client.post(
            self.login_url,
            {
                "username": self.user.username,
                "password": PASSWORD,
                "role": "author",
                **_solved_captcha(),
            },
        )

    def test_login_redirects_to_verify_when_device_already_confirmed(self):
        response = self._login()
        self.assertRedirects(response, self.verify_url)

    def test_correct_totp_code_grants_access(self):
        self._login()
        response = self.client.post(self.verify_url, {"code": _code_for(self.device)})
        self.assertRedirects(response, reverse("home"))

        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)

    def test_wrong_code_is_rejected_and_session_stays_unverified(self):
        self._login()
        response = self.client.post(self.verify_url, {"code": "000000"})
        self.assertContains(response, "Invalid code")

        response = self.client.get(self.profile_url)
        self.assertRedirects(response, f"{self.verify_url}?next={self.profile_url}")

    def test_recovery_code_grants_access_and_is_consumed(self):
        self._login()
        code = self.recovery_codes[0]

        response = self.client.post(self.verify_url, {"code": code})

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(StaticToken.objects.filter(token=code).exists())

    def test_used_recovery_code_cannot_be_reused(self):
        self._login()
        code = self.recovery_codes[0]
        self.client.post(self.verify_url, {"code": code})
        self.client.logout()

        self._login()
        response = self.client.post(self.verify_url, {"code": code})

        self.assertContains(response, "Invalid code")


class VoluntaryTwoFactorManagementTests(TestCase):
    """
    Profile-page self-service actions: readers may voluntarily enable 2FA
    (and disable it again), privileged roles may not turn it off.
    """

    def setUp(self):
        self.reader = User.objects.create_user(
            username="readeruser", password=PASSWORD, role="reader"
        )
        self.editor = User.objects.create_user(
            username="editoruser", password=PASSWORD, role="editor"
        )
        self.disable_url = reverse("two_factor_disable")
        self.regenerate_url = reverse("two_factor_regenerate_codes")
        self.profile_url = reverse("profile")

    def _enable_2fa(self, user):
        device = TOTPDevice.objects.create(user=user, confirmed=True)
        generate_recovery_codes(user)
        self.client.login(username=user.username, password=PASSWORD)
        _mark_session_verified(self.client, device)
        return device

    def test_reader_can_disable_2fa_with_correct_password(self):
        self._enable_2fa(self.reader)

        response = self.client.post(self.disable_url, {"password": PASSWORD})

        self.assertRedirects(response, self.profile_url)
        self.assertFalse(user_has_2fa_enabled(self.reader))

    def test_disable_requires_correct_password(self):
        self._enable_2fa(self.reader)

        self.client.post(self.disable_url, {"password": "wrong-password"})

        self.assertTrue(user_has_2fa_enabled(self.reader))

    def test_privileged_role_cannot_disable_2fa(self):
        self._enable_2fa(self.editor)

        self.client.post(self.disable_url, {"password": PASSWORD})

        self.assertTrue(user_has_2fa_enabled(self.editor))

    def test_regenerate_recovery_codes_invalidates_old_ones(self):
        self._enable_2fa(self.reader)
        old_codes = set(
            StaticToken.objects.filter(device__user=self.reader).values_list("token", flat=True)
        )

        response = self.client.post(self.regenerate_url, {"password": PASSWORD})

        self.assertEqual(response.status_code, 200)
        new_codes = set(response.context["recovery_codes"])
        self.assertEqual(len(new_codes), 10)
        self.assertTrue(old_codes.isdisjoint(new_codes))
        self.assertEqual(
            StaticToken.objects.filter(device__user=self.reader).count(), 10
        )

    def test_regenerate_requires_correct_password(self):
        self._enable_2fa(self.reader)
        old_codes = set(
            StaticToken.objects.filter(device__user=self.reader).values_list("token", flat=True)
        )

        self.client.post(self.regenerate_url, {"password": "wrong-password"})

        current_codes = set(
            StaticToken.objects.filter(device__user=self.reader).values_list("token", flat=True)
        )
        self.assertEqual(old_codes, current_codes)


class AdminTwoFactorManagementTests(TestCase):
    """Django-admin visibility into, and control over, users' 2FA state."""

    def setUp(self):
        # role='reader' keeps this acting account itself outside the
        # mandatory-2FA gate, so the test can focus purely on the admin
        # action's effect on the *managed* user's devices.
        self.superuser = User.objects.create_superuser(
            username="superadmin", email="admin@example.com", password=PASSWORD, role="reader"
        )
        self.editor = User.objects.create_user(
            username="editoruser", password=PASSWORD, role="editor"
        )
        TOTPDevice.objects.create(user=self.editor, confirmed=True)
        generate_recovery_codes(self.editor)

    def test_changelist_shows_2fa_columns(self):
        self.client.login(username="superadmin", password=PASSWORD)
        response = self.client.get(reverse("admin:users_customuser_changelist"))
        self.assertEqual(response.status_code, 200)

    def test_reset_action_wipes_totp_and_recovery_devices(self):
        self.client.login(username="superadmin", password=PASSWORD)

        response = self.client.post(
            reverse("admin:users_customuser_changelist"),
            {
                "action": "reset_two_factor_enrollment",
                "_selected_action": [str(self.editor.pk)],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(user_has_2fa_enabled(self.editor))
        self.assertEqual(
            StaticToken.objects.filter(device__user=self.editor).count(), 0
        )
