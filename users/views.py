import base64
import io
from base64 import b32encode
from urllib.parse import quote

import qrcode
from django_otp import login as otp_login

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import RegisterForm, ProfileUpdateForm, LoginCaptchaForm, TwoFactorCodeForm
from .security import (
    get_client_ip,
    record_attempt,
    check_lockout,
    lockout_message,
    requires_captcha,
    safe_next_url,
)
from .twofactor import (
    two_factor_gate,
    user_requires_2fa,
    user_has_2fa_enabled,
    get_confirmed_totp_device,
    get_or_create_pending_totp_device,
    generate_recovery_codes,
    recovery_codes_remaining,
    reset_2fa_for_user,
    RECOVERY_DEVICE_NAME,
)
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice

import logging
logger = logging.getLogger("users")
security_logger = logging.getLogger("security")


def _record_failure_and_get_error(username, ip_address, reason):
    """
    Records a failed attempt, then re-checks lockout so a failure that just
    tripped the threshold is reported immediately instead of requiring one
    more attempt to notice. Always returns the same generic message for
    non-locked failures, regardless of `reason`.
    """
    record_attempt(username, ip_address, successful=False, reason=reason)

    locked, unlock_at = check_lockout(username)
    if locked:
        security_logger.warning(
            "Account locked after repeated failures: '%s' from IP %s",
            username,
            ip_address,
        )
        return lockout_message(unlock_at)

    return "Invalid credentials"


def _maybe_captcha_form(username):
    """
    A fresh, unbound LoginCaptchaForm if `username` now needs one on its
    next attempt, otherwise None. Called after recording a failure so a
    failure that just crossed the CAPTCHA threshold shows the field
    immediately, same pattern as the lockout re-check.
    """
    return LoginCaptchaForm() if requires_captcha(username) else None


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            logger.info(f"New user registered: {user.username}")

            login(request, user)
            logger.info(f"User logged in immediately after registration: {user.username}")

            return redirect('/')
        else:
            security_logger.warning(
                f"Failed registration attempt from IP {request.META.get('REMOTE_ADDR')}"
            )
    else:
        form = RegisterForm()

    return render(
        request,
        'users/register.html',
        {'form': form}
    )

PUBLIC_LOGIN_ROLES = ("editor", "author", "reader")


def login_view(request):
    # `next` can arrive via querystring (GET, e.g. ?next=/posts/my-slug/)
    # or as a hidden field re-submitted with the POST.
    next_url = request.POST.get("next") or request.GET.get("next")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        role = request.POST.get("role")
        ip_address = get_client_ip(request)

        # Checked before anything else touches credentials, so a locked
        # account never reaches authenticate() while it's locked.
        locked, unlock_at = check_lockout(username)
        if locked:
            record_attempt(username, ip_address, successful=False, reason="locked_out")
            security_logger.warning(
                "Login blocked - account locked: '%s' from IP %s (unlocks %s)",
                username,
                ip_address,
                unlock_at.isoformat(),
            )
            return render(
                request,
                "users/login.html",
                {"error": lockout_message(unlock_at), "next": next_url},
            )

        # Progressive CAPTCHA: once a username's recent failures cross
        # LOGIN_CAPTCHA_AFTER_ATTEMPTS, the next attempt must include a
        # solved CAPTCHA before role/credentials are even checked - a
        # wrong CAPTCHA is treated exactly like a wrong password.
        if requires_captcha(username):
            captcha_form = LoginCaptchaForm(request.POST)
            if not captcha_form.is_valid():
                security_logger.warning(
                    "Login blocked - invalid CAPTCHA for '%s' from IP %s", username, ip_address,
                )
                record_attempt(username, ip_address, successful=False, reason="captcha_failed")

                locked, unlock_at = check_lockout(username)
                if locked:
                    security_logger.warning(
                        "Account locked after repeated failures: '%s' from IP %s",
                        username,
                        ip_address,
                    )
                    return render(
                        request,
                        "users/login.html",
                        {"error": lockout_message(unlock_at), "next": next_url},
                    )

                return render(
                    request,
                    "users/login.html",
                    {
                        "error": "Incorrect CAPTCHA. Please try again.",
                        "next": next_url,
                        "captcha_form": LoginCaptchaForm(),
                    },
                )

        if role not in PUBLIC_LOGIN_ROLES:
            security_logger.warning(
                "Login attempt with invalid role '%s' for '%s' from IP %s",
                role,
                username,
                ip_address,
            )
            error = _record_failure_and_get_error(username, ip_address, "invalid_role")
            return render(
                request,
                "users/login.html",
                {"error": error, "next": next_url, "captcha_form": _maybe_captcha_form(username)},
            )

        user = authenticate(request, username=username, password=password)

        # Reject on missing user OR role mismatch, but always show the same
        # generic error - a role-specific message would let an attacker use
        # the login form to enumerate which role a given account holds.
        if user is None or user.role != role:
            security_logger.warning(
                "Failed login attempt for '%s' (role '%s') from IP %s",
                username,
                role,
                ip_address,
            )
            reason = "invalid_credentials" if user is None else "role_mismatch"
            error = _record_failure_and_get_error(username, ip_address, reason)
            return render(
                request,
                "users/login.html",
                {"error": error, "next": next_url, "captcha_form": _maybe_captcha_form(username)},
            )

        record_attempt(username, ip_address, successful=True)
        login(request, user)
        logger.info("User logged in successfully: %s", user.username)

        safe_next = safe_next_url(request, next_url)

        # A fresh password login never carries an OTP verification with it,
        # so anyone with 2FA enabled (voluntarily or because their role
        # requires it) or still owing a mandatory enrollment is routed
        # there before anywhere else. See
        # users.middleware.TwoFactorEnforcementMiddleware for the backstop
        # that also covers logins that don't go through this view (e.g.
        # /admin/) and any later request in an unverified session.
        gate = two_factor_gate(user)
        if gate:
            two_factor_url = reverse(f"two_factor_{gate}")
            if safe_next:
                two_factor_url = f"{two_factor_url}?next={quote(safe_next)}"
            return redirect(two_factor_url)

        if safe_next:
            return redirect(safe_next)

        return redirect("home")

    return render(request, "users/login.html", {"next": next_url})


@require_POST
@login_required
def logout_view(request):
    logger.info(f"User logged out: {request.user.username}")
    logout(request)
    return redirect("home")


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=request.user
        )

        if form.is_valid():
            form.save()
            logger.info(f"Profile updated: {request.user.username}")
            return redirect('profile')
        else:
            security_logger.warning(
                f"Invalid profile update attempt by {request.user.username}"
            )
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(
        request,
        'users/profile.html',
        {
            'form': form,
            'two_factor_enabled': user_has_2fa_enabled(request.user),
            'two_factor_required': user_requires_2fa(request.user),
            'recovery_codes_remaining': recovery_codes_remaining(request.user),
        }
    )


@require_POST
@login_required
def delete_account(request):
    password = request.POST.get("password")
    user = request.user

    if not user.check_password(password):
        security_logger.warning(
            f"Failed account deletion attempt (incorrect password) by {user.username}"
        )
        form = ProfileUpdateForm(instance=user)
        return render(
            request,
            'users/profile.html',
            {
                'form': form,
                'delete_error': "Incorrect password. Your account was not deleted.",
            }
        )

    username = user.username
    logout(request)
    user.delete()
    logger.info(f"Account deleted: {username}")

    messages.success(request, "Your account has been permanently deleted.")
    return redirect('home')


def _qr_data_uri(data):
    """A `data:image/png;base64,...` URI for the given otpauth:// URL."""
    img = qrcode.make(data, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _manual_key(device):
    """The device's secret as the spaced base32 string authenticator apps
    expect for manual entry - the same value encoded in the QR code."""
    raw = b32encode(device.bin_key).decode("utf-8")
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def _totp_throttle_message(device):
    """None if a verify attempt is currently allowed, otherwise a message
    explaining how long to wait - django_otp throttles both TOTP and
    recovery-code devices with exponential backoff after repeated
    failures."""
    allowed, extra = device.verify_is_allowed()
    if allowed:
        return None

    locked_until = (extra or {}).get("locked_until")
    if locked_until:
        seconds = max(1, int((locked_until - timezone.now()).total_seconds()))
        return f"Too many incorrect attempts. Please wait {seconds} second(s) and try again."

    return "Too many incorrect attempts. Please wait a moment and try again."


@login_required
def two_factor_setup(request):
    """
    First-time TOTP enrollment. Reachable by any authenticated user who
    hasn't enabled 2FA yet - mandatory for privileged roles (see
    users.twofactor.TWO_FACTOR_REQUIRED_ROLES and
    users.middleware.TwoFactorEnforcementMiddleware, which redirects them
    here), optional for everyone else via the profile page.

    A device is created unconfirmed and only flipped to confirmed - i.e.
    actually enrolled - once the user proves they can generate a valid
    code with it. Recovery codes are issued in the same step, immediately
    after confirmation, and shown exactly once.
    """
    user = request.user

    if user_has_2fa_enabled(user):
        messages.info(request, "Two-factor authentication is already enabled on your account.")
        return redirect("profile")

    next_url = safe_next_url(request, request.POST.get("next") or request.GET.get("next"))
    device = get_or_create_pending_totp_device(user)

    if request.method == "POST":
        form = TwoFactorCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]

            if device.verify_token(code):
                device.confirmed = True
                device.save(update_fields=["confirmed"])

                # Abandoned setup attempts (e.g. a previous unconfirmed
                # device from a QR the user never scanned) shouldn't
                # linger once enrollment actually succeeds.
                TOTPDevice.objects.filter(
                    user=user, confirmed=False
                ).exclude(pk=device.pk).delete()

                recovery_codes = generate_recovery_codes(user)
                otp_login(request, device)

                logger.info("2FA enabled: %s", user.username)
                security_logger.info(
                    "2FA enrollment completed for '%s' from IP %s",
                    user.username,
                    get_client_ip(request),
                )

                return render(
                    request,
                    "users/two_factor_recovery_codes.html",
                    {
                        "recovery_codes": recovery_codes,
                        "next": next_url,
                        "just_enrolled": True,
                    },
                )

            security_logger.warning(
                "2FA setup: invalid code entered by '%s' from IP %s",
                user.username,
                get_client_ip(request),
            )
            form.add_error(
                "code",
                "Incorrect code. Check your authenticator app and try again.",
            )
    else:
        form = TwoFactorCodeForm()

    return render(
        request,
        "users/two_factor_setup.html",
        {
            "form": form,
            "qr_data_uri": _qr_data_uri(device.config_url),
            "manual_key": _manual_key(device),
            "next": next_url,
            "required": user_requires_2fa(user),
        },
    )


@login_required
def two_factor_verify(request):
    """
    Per-session OTP check for a user who already has a confirmed TOTP
    device - shown right after every fresh password login (their session
    starts out unverified regardless of role) and re-enforced on any
    later request by TwoFactorEnforcementMiddleware. Accepts either the
    authenticator app's current code or one of the user's unused recovery
    codes.
    """
    user = request.user
    device = get_confirmed_totp_device(user)

    if device is None:
        return redirect("two_factor_setup")

    next_url = safe_next_url(request, request.POST.get("next") or request.GET.get("next"))

    if request.method == "POST":
        form = TwoFactorCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]
            error = _totp_throttle_message(device)

            if error is None:
                if device.verify_token(code):
                    otp_login(request, device)
                    logger.info("2FA verified: %s", user.username)
                    return redirect(next_url or "home")

                recovery_device = StaticDevice.objects.filter(
                    user=user, name=RECOVERY_DEVICE_NAME
                ).first()
                recovery_error = (
                    _totp_throttle_message(recovery_device) if recovery_device else None
                )

                if recovery_device and recovery_error is None and recovery_device.verify_token(code):
                    otp_login(request, recovery_device)
                    remaining = recovery_codes_remaining(user)
                    security_logger.warning(
                        "2FA verified with a recovery code for '%s' from IP %s (%d code(s) left)",
                        user.username,
                        get_client_ip(request),
                        remaining,
                    )
                    messages.warning(
                        request,
                        f"You signed in with a recovery code. {remaining} recovery "
                        "code(s) remain - regenerate them soon if you're running low.",
                    )
                    return redirect(next_url or "home")

                error = recovery_error

            if error is None:
                error = "Invalid code. Please try again."

            security_logger.warning(
                "2FA verification failed for '%s' from IP %s",
                user.username,
                get_client_ip(request),
            )
            form.add_error("code", error)
    else:
        form = TwoFactorCodeForm()

    return render(
        request,
        "users/two_factor_verify.html",
        {"form": form, "next": next_url},
    )


@require_POST
@login_required
def two_factor_disable(request):
    """
    Voluntary opt-out, only ever available to users whose role doesn't
    mandate 2FA - privileged roles have no self-service way to turn it
    off (see users/twofactor.py). Requires the current password, same
    pattern as delete_account.
    """
    user = request.user

    if user_requires_2fa(user):
        security_logger.warning(
            "Blocked 2FA disable attempt for privileged user '%s'", user.username
        )
        messages.error(request, "Two-factor authentication is required for your role and can't be disabled.")
        return redirect("profile")

    if not user.check_password(request.POST.get("password")):
        security_logger.warning(
            "Failed 2FA disable attempt (incorrect password) by '%s'", user.username
        )
        messages.error(request, "Incorrect password. Two-factor authentication was not disabled.")
        return redirect("profile")

    reset_2fa_for_user(user)
    logger.info("2FA disabled: %s", user.username)
    security_logger.info("2FA disabled for '%s' from IP %s", user.username, get_client_ip(request))
    messages.success(request, "Two-factor authentication has been disabled.")
    return redirect("profile")


@require_POST
@login_required
def two_factor_regenerate_codes(request):
    """Issues a fresh batch of recovery codes, invalidating the old ones."""
    user = request.user

    if not user_has_2fa_enabled(user):
        messages.error(request, "Two-factor authentication isn't enabled on your account.")
        return redirect("profile")

    if not user.check_password(request.POST.get("password")):
        security_logger.warning(
            "Failed recovery code regeneration attempt (incorrect password) by '%s'", user.username
        )
        messages.error(request, "Incorrect password. Recovery codes were not regenerated.")
        return redirect("profile")

    recovery_codes = generate_recovery_codes(user)
    security_logger.info(
        "Recovery codes regenerated for '%s' from IP %s", user.username, get_client_ip(request)
    )

    return render(
        request,
        "users/two_factor_recovery_codes.html",
        {"recovery_codes": recovery_codes, "just_enrolled": False},
    )
