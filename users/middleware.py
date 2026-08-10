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
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.utils import timezone

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
