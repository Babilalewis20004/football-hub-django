import logging

from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from captcha.fields import CaptchaField

from .models import CustomUser
from .security import (
    get_client_ip,
    record_attempt,
    check_lockout,
    lockout_message,
    requires_captcha,
)

logger = logging.getLogger("users")
security_logger = logging.getLogger("security")


class RegisterForm(UserCreationForm):

    email = forms.EmailField()
    captcha = CaptchaField()

    class Meta:
        model = CustomUser

        fields = (
            'username',
            'email',
            'password1',
            'password2'
        )


class LoginCaptchaForm(forms.Form):
    """
    Standalone CAPTCHA-only form used by the public login view. Kept
    separate from username/password (which login_view reads straight off
    request.POST) because it's only instantiated - and only needs to
    validate - once users.security.requires_captcha() says the username
    being attempted has enough recent failures to warrant one.
    """

    captcha = CaptchaField()


class TwoFactorCodeForm(forms.Form):
    """
    A single code field used both when confirming a brand-new TOTP device
    (setup) and when verifying an already-enrolled one (login). Accepts
    either a 6-digit authenticator code or an 8-character recovery code -
    the view tries both against the user's devices, so this form doesn't
    need to know which kind was entered.
    """

    code = forms.CharField(
        label="Authentication code",
        max_length=16,
        widget=forms.TextInput(attrs={
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "autofocus": True,
            "class": "form-control login-input",
        }),
    )


class ProfileUpdateForm(forms.ModelForm):

    class Meta:
        model = CustomUser

        fields = (
            'avatar',
            'bio',
            'favorite_team'
        )


class LockoutAwareAdminAuthenticationForm(AdminAuthenticationForm):
    """
    Applies the same failed-attempt lockout as the public login view
    (users.security) to the Django admin login, so /admin/ can't be used
    to route around it. Lockout state is shared with the public view -
    it's keyed on the submitted username, not on which form was used -
    since both are attempts against the same account.

    Also mirrors the public view's progressive CAPTCHA: once a username
    has enough recent failures (users.security.requires_captcha), a
    `captcha` field is added to the form and must be solved correctly
    before credentials are even checked. See templates/admin/login.html
    for the matching template override that renders it.
    """

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request=request, *args, **kwargs)
        username = self.data.get("username") if self.data else None
        if requires_captcha(username):
            self.fields["captcha"] = CaptchaField()

    def clean(self):
        username = self.cleaned_data.get("username") or self.data.get("username", "")
        ip_address = get_client_ip(self.request)

        locked, unlock_at = check_lockout(username)
        if locked:
            record_attempt(username, ip_address, successful=False, reason="admin_locked_out")
            security_logger.warning(
                "Admin login blocked - account locked: '%s' from IP %s (unlocks %s)",
                username,
                ip_address,
                unlock_at.isoformat(),
            )
            raise ValidationError(lockout_message(unlock_at), code="locked_out")

        # Checked separately from the rest of field validation so a wrong
        # CAPTCHA never lets execution reach super().clean() - that call
        # authenticates against real credentials, which we don't want to
        # attempt at all until the CAPTCHA has been solved.
        if self.errors.get("captcha"):
            record_attempt(username, ip_address, successful=False, reason="admin_captcha_failed")
            security_logger.warning(
                "Admin login blocked - invalid CAPTCHA for '%s' from IP %s", username, ip_address,
            )

            locked, unlock_at = check_lockout(username)
            if locked:
                raise ValidationError(lockout_message(unlock_at), code="locked_out")
            raise ValidationError("Incorrect CAPTCHA. Please try again.", code="invalid_captcha")

        try:
            cleaned_data = super().clean()
        except ValidationError:
            record_attempt(username, ip_address, successful=False, reason="admin_invalid_login")
            security_logger.warning(
                "Failed admin login attempt for '%s' from IP %s", username, ip_address,
            )

            # This failure may have just tripped the lockout threshold -
            # surface that immediately instead of waiting for one more try.
            locked, unlock_at = check_lockout(username)
            if locked:
                security_logger.warning(
                    "Account locked after repeated admin login failures: '%s' from IP %s",
                    username,
                    ip_address,
                )
                raise ValidationError(lockout_message(unlock_at), code="locked_out")
            raise

        record_attempt(username, ip_address, successful=True, reason="admin_success")
        logger.info("Admin login successful: %s", username)
        return cleaned_data
