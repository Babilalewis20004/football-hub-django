"""
Two-factor authentication (TOTP) helpers built on django-otp.

django-otp supplies the actual cryptographic TOTP implementation
(django_otp.plugins.otp_totp.models.TOTPDevice) and the recovery-code
mechanism (django_otp.plugins.otp_static.models.StaticDevice/StaticToken) -
nothing here re-implements any of that. This module just encodes this
project's policy on top of those primitives: who is required to enrol,
how a device moves from "provisioned" to "confirmed", and how recovery
codes are (re)issued.

Roles that must complete TOTP enrollment before doing anything else -
mirrors users.signals.SINGLE_SESSION_ROLES, the existing boundary this
codebase already draws between privileged and unprivileged accounts.
"""
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken

TWO_FACTOR_REQUIRED_ROLES = {"admin", "editor", "author"}

RECOVERY_CODE_COUNT = 10
RECOVERY_DEVICE_NAME = "recovery-codes"
TOTP_DEVICE_NAME = "authenticator-app"


def user_requires_2fa(user) -> bool:
    """Whether this user's role mandates TOTP enrollment before continuing."""
    return getattr(user, "role", None) in TWO_FACTOR_REQUIRED_ROLES


def get_confirmed_totp_device(user):
    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


def user_has_2fa_enabled(user) -> bool:
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists()


def two_factor_gate(user):
    """
    What, if anything, a user must do about 2FA before continuing past
    login: 'verify' if they already have a confirmed device (whether
    because their role requires it or because they opted in voluntarily -
    once enabled, it's always checked), 'setup' if their role mandates
    enrollment and they haven't completed it yet, or None if neither
    applies (the default for unprivileged users who haven't opted in).
    """
    if user_has_2fa_enabled(user):
        return "verify"
    if user_requires_2fa(user):
        return "setup"
    return None


def get_or_create_pending_totp_device(user):
    """
    The single in-progress (unconfirmed) TOTP device for a user, creating
    one if none exists yet. Confirmed devices are never touched here - this
    is only for the enrollment step, before a device is activated.
    """
    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(
            user=user, name=TOTP_DEVICE_NAME, confirmed=False
        )
    return device


def generate_recovery_codes(user):
    """
    Issues a fresh batch of one-time recovery codes, replacing any that
    existed before (old codes are invalidated the moment new ones are
    generated - there is never more than one valid batch at a time).

    Returns the plaintext codes. This is the only point at which they are
    ever available in plaintext outside the database - callers must display
    them to the user immediately and not persist them anywhere themselves.
    """
    StaticDevice.objects.filter(user=user, name=RECOVERY_DEVICE_NAME).delete()
    device = StaticDevice.objects.create(
        user=user, name=RECOVERY_DEVICE_NAME, confirmed=True
    )

    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        token = StaticToken.random_token()
        StaticToken.objects.create(device=device, token=token)
        codes.append(token)

    return codes


def recovery_codes_remaining(user) -> int:
    return StaticToken.objects.filter(
        device__user=user, device__name=RECOVERY_DEVICE_NAME
    ).count()


def reset_2fa_for_user(user):
    """
    Wipes all TOTP and recovery-code devices for a user, forcing them back
    through enrollment next time they're subject to it. Used by admin
    "reset 2FA enrollment" management and by the user's own "disable 2FA".
    """
    TOTPDevice.objects.filter(user=user).delete()
    StaticDevice.objects.filter(user=user, name=RECOVERY_DEVICE_NAME).delete()
