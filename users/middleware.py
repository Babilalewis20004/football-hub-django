"""
Inactivity-based session timeout.

SESSION_COOKIE_AGE alone only bounds how long a session can live since it
was last *saved*; with SESSION_SAVE_EVERY_REQUEST it becomes a genuine
inactivity window at the storage layer, but Django expires that session
silently - the next request just looks logged-out, with no message
explaining why.

This middleware stamps the timestamp of a user's last authenticated
request into their own session, so the 5-minute window resets on every
request rather than counting down from login. When more time than
SESSION_INACTIVITY_TIMEOUT has passed since that timestamp, it logs the
user out itself and surfaces a message, so the login page can explain
what happened instead of a silent redirect.
"""
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from .twofactor import two_factor_gate

SESSION_INACTIVITY_TIMEOUT = getattr(settings, "SESSION_INACTIVITY_TIMEOUT", 300)
LAST_ACTIVITY_SESSION_KEY = "last_activity"

SESSION_TIMEOUT_MESSAGE = "Your session expired due to inactivity. Please log in again."


class SessionInactivityTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now().timestamp()
            last_activity = request.session.get(LAST_ACTIVITY_SESSION_KEY)

            if last_activity is not None and now - last_activity > SESSION_INACTIVITY_TIMEOUT:
                logout(request)
                messages.error(request, SESSION_TIMEOUT_MESSAGE)
            else:
                request.session[LAST_ACTIVITY_SESSION_KEY] = now

        return self.get_response(request)


class TwoFactorEnforcementMiddleware:
    """
    Backstop that keeps an authenticated user from reaching anything else
    while they owe a mandatory TOTP enrollment or an OTP verification for
    this session - regardless of which login path put them in that state.

    users.views.login_view already redirects straight to the right 2FA
    step immediately after a successful password login, but that alone
    isn't enough: it doesn't cover the separate /admin/ login form (which
    calls django.contrib.auth.login() directly, bypassing this view
    entirely), and it can't stop a user from later navigating straight to
    a bookmarked URL in an unverified session. This middleware runs on
    every request instead, after django_otp.middleware.OTPMiddleware has
    populated request.user.is_verified().
    """

    EXEMPT_URL_NAMES = {"two_factor_setup", "two_factor_verify", "logout"}

    # Requests that shouldn't be hijacked even though they're not part of
    # the 2FA flow itself: the CSP violation beacon is fired automatically
    # by the browser, not navigated to by the user.
    EXEMPT_PATH_PREFIXES = ("/csp-report/",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if user.is_authenticated and not self._is_exempt(request):
            gate = two_factor_gate(user)

            if gate == "setup":
                return self._redirect_to(request, "two_factor_setup")

            if gate == "verify" and not user.is_verified():
                return self._redirect_to(request, "two_factor_verify")

        return self.get_response(request)

    def _is_exempt(self, request):
        if request.path.startswith(self.EXEMPT_PATH_PREFIXES):
            return True

        try:
            url_name = resolve(request.path).url_name
        except Resolver404:
            return False

        return url_name in self.EXEMPT_URL_NAMES

    @staticmethod
    def _redirect_to(request, view_name):
        target = reverse(view_name)
        if request.method == "GET":
            target = f"{target}?next={quote(request.get_full_path())}"
        return redirect(target)
