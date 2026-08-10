"""
Role-based single-session enforcement.

Admin/editor/author accounts hold elevated privileges, so each one may
have only one active session at a time: a fresh login evicts any other
sessions that account already holds. Readers are unprivileged and may
stay logged in on multiple devices/browsers simultaneously.

Sessions are DB-backed (django.contrib.sessions.backends.db) and the
Session model has no user_id column, so the only way to find a user's
other sessions is to decode each active row and check its
_auth_user_id - the standard approach for this without a dedicated
session-tracking model.

Hooking this to user_logged_in (rather than the login view itself)
means it applies uniformly no matter which code path calls
django.contrib.auth.login() - including the separate /admin/ login
form, which the public login view's role gate never touches.
"""
from django.contrib.auth.signals import user_logged_in
from django.contrib.sessions.models import Session
from django.dispatch import receiver
from django.utils import timezone

SINGLE_SESSION_ROLES = {"admin", "editor", "author"}


@receiver(user_logged_in)
def enforce_single_session(sender, request, user, **kwargs):
    if user.role not in SINGLE_SESSION_ROLES:
        return

    current_session_key = request.session.session_key
    other_sessions = Session.objects.filter(expire_date__gte=timezone.now())
    if current_session_key:
        other_sessions = other_sessions.exclude(session_key=current_session_key)

    stale_keys = [
        session.session_key
        for session in other_sessions
        if session.get_decoded().get("_auth_user_id") == str(user.pk)
    ]
    if stale_keys:
        Session.objects.filter(session_key__in=stale_keys).delete()
