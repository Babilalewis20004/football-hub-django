from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import RegisterForm, ProfileUpdateForm

import logging
logger = logging.getLogger("users")
security_logger = logging.getLogger("security")


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

        if role not in PUBLIC_LOGIN_ROLES:
            security_logger.warning(
                "Login attempt with invalid role '%s' for '%s' from IP %s",
                role,
                username,
                request.META.get("REMOTE_ADDR"),
            )
            return render(
                request,
                "users/login.html",
                {"error": "Invalid credentials", "next": next_url},
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
                request.META.get("REMOTE_ADDR"),
            )
            return render(
                request,
                "users/login.html",
                {"error": "Invalid credentials", "next": next_url},
            )

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
