"""
Login-attempt tracking and account lockout.

The lockout state is derived entirely from the LoginAttempt audit table
rather than stored as a counter on CustomUser: an account (identified by
the submitted username string) is considered locked when its most recent
LOGIN_MAX_FAILED_ATTEMPTS attempts were all failures and the latest one
happened within the LOGIN_LOCKOUT_MINUTES window. A successful attempt
breaks the streak, which is how the counter "resets" on successful login.

Because lockout is keyed on the submitted username rather than on whether
that username maps to a real CustomUser, nonexistent usernames lock out
the same way real ones do - the login view's response is identical either
way, so it can't be used to enumerate valid accounts.
"""
import math
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .models import LoginAttempt

MAX_FAILED_ATTEMPTS = getattr(settings, "LOGIN_MAX_FAILED_ATTEMPTS", 5)
LOCKOUT_DURATION = timedelta(minutes=getattr(settings, "LOGIN_LOCKOUT_MINUTES", 15))
CAPTCHA_AFTER_ATTEMPTS = getattr(settings, "LOGIN_CAPTCHA_AFTER_ATTEMPTS", 2)

LOCKOUT_MESSAGE_TEMPLATE = (
    "Too many failed login attempts. This account has been temporarily "
    "locked for security reasons. Please try again in {minutes} minute(s)."
)


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_attempt(username, ip_address, successful, reason=""):
    return LoginAttempt.objects.create(
        username=(username or "").strip(),
        ip_address=ip_address,
        successful=successful,
        reason=reason,
    )


def check_lockout(username):
    """
    Returns (is_locked, unlock_at). `unlock_at` is None when not locked.
    """
    username = (username or "").strip()
    if not username:
        return False, None

    recent = list(
        LoginAttempt.objects.filter(username=username)
        .order_by("-timestamp")[:MAX_FAILED_ATTEMPTS]
    )

    if len(recent) < MAX_FAILED_ATTEMPTS or any(attempt.successful for attempt in recent):
        return False, None

    unlock_at = recent[0].timestamp + LOCKOUT_DURATION
    if timezone.now() >= unlock_at:
        return False, None

    return True, unlock_at


def failed_streak(username):
    """
    Number of consecutive most-recent failed attempts for `username`,
    capped at MAX_FAILED_ATTEMPTS. A successful attempt anywhere in that
    window breaks the streak, mirroring check_lockout()'s notion of
    "recent failures" so the two stay in sync.
    """
    username = (username or "").strip()
    if not username:
        return 0

    recent = LoginAttempt.objects.filter(username=username).order_by("-timestamp")[
        :MAX_FAILED_ATTEMPTS
    ]

    streak = 0
    for attempt in recent:
        if attempt.successful:
            break
        streak += 1
    return streak


def requires_captcha(username):
    """
    Whether the next login attempt for `username` must include a valid
    CAPTCHA, based on its recent failure streak. Kicks in before the
    account locks out, so a human gets a chance to prove they're human
    before being locked out entirely.
    """
    return failed_streak(username) >= CAPTCHA_AFTER_ATTEMPTS


def safe_next_url(request, candidate):
    """
    `candidate` if it's a safe, same-site relative URL to redirect to after
    login (or after the 2FA step that follows it), otherwise None. Never
    redirect straight to a user-supplied URL unchecked - that's an
    open-redirect vector (e.g. ?next=https://evil.example.com).
    """
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return None


def minutes_remaining(unlock_at):
    return max(1, math.ceil((unlock_at - timezone.now()).total_seconds() / 60))


def lockout_message(unlock_at):
    return LOCKOUT_MESSAGE_TEMPLATE.format(minutes=minutes_remaining(unlock_at))
