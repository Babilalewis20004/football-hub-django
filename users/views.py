from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import RegisterForm, ProfileUpdateForm, LoginCaptchaForm
from .security import (
    get_client_ip,
    record_attempt,
    check_lockout,
    lockout_message,
    requires_captcha,
)

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

        # Only redirect to `next` if it's a safe, same-site relative URL.
        # Never redirect straight to a user-supplied URL unchecked ---
        # that's an open-redirect vector (e.g. ?next=https://evil.example.com).
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)

        return redirect("dashboard")

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
        {'form': form}
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
