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
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in
from django.contrib.sessions.models import Session
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import CustomUser

SINGLE_SESSION_ROLES = {"admin", "editor", "author"}

# Single source of truth for the role<->Group mapping: CustomUser.ROLE_CHOICES
# already pairs each stored role value with the exact display name used as
# the matching Group name (Admin/Editor/Author/Contributor/Reader), so there's
# no separate list to keep in sync by hand.
ROLE_GROUP_NAMES = dict(CustomUser.ROLE_CHOICES)
VALID_ROLES = frozenset(ROLE_GROUP_NAMES)


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


def apply_role_group(user):
    """
    Make `user`'s Django Group membership match `user.role`: add the one
    Group that corresponds to their current role and remove any of the
    other four application-role Groups they're still sitting in, so a role
    change never leaves a user in two roles' Groups at once (e.g. still in
    "Editor" after being demoted to "Reader").

    Centralised here so both the post_save signal below (the normal path,
    on every role change made through the app or Django admin) and
    users.management.commands.backfill_user_roles (the one-off repair path
    for accounts whose Group membership drifted from `role` before this
    sync existed) share one implementation instead of duplicating the
    add/remove logic.

    Returns True if membership actually changed, False if it already
    matched (or the role isn't a recognised one).
    """
    group_name = ROLE_GROUP_NAMES.get(user.role)
    if group_name is None:
        return False

    current_role_groups = set(
        user.groups.filter(name__in=ROLE_GROUP_NAMES.values()).values_list("name", flat=True)
    )
    if current_role_groups == {group_name}:
        return False

    target_group, _ = Group.objects.get_or_create(name=group_name)
    stale_group_names = current_role_groups - {group_name}
    stale_groups = user.groups.filter(name__in=stale_group_names)

    user.groups.remove(*stale_groups)
    user.groups.add(target_group)
    return True


@receiver(post_save, sender=CustomUser)
def sync_role_group(sender, instance, created, raw, **kwargs):
    """
    Blog permissions (blog.add_post, blog.can_publish_post, etc.) are
    granted through Django Group membership, not the `role` field
    directly - see blog/management/commands/setup_roles.py. Without
    this, changing `role` silently leaves group membership (and thus
    permissions) unchanged, which is how accounts end up with a role
    that doesn't match what they can actually do.

    Only acts when `role` actually changed (or the user is new) rather
    than on every save - CustomUser gets saved for all sorts of unrelated
    reasons (login's last_login update, profile edits, 2FA toggles), and
    those shouldn't silently strip out group membership that was set up
    independently of `role`.
    """
    if raw:
        return

    if not created and instance.role == instance._loaded_role:
        return

    apply_role_group(instance)
    instance._loaded_role = instance.role
