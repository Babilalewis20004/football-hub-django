# Authentication (Login, Register, Password Reset)

## Login

**Template:** `templates/users/login.html`
**Route:** `/login/` (`users.views.login_view`, name=`login`)
**Users/roles:** Public/anonymous.

```text
+----------------------------------------------------+
| MASTHEAD / NAVBAR                                   |
+----------------------------------------------------+
|                  [ Login ]                          |
|                                                      |
|   Username: [......................]                |
|   Password: [......................]                |
|   Role:     [ Editor v ] (select: Editor/Author/Contributor/Reader) |
|                                                      |
|   {% if captcha_form %}                              |
|   CAPTCHA image: [ 8 x k 3 f ]  Enter: [........]     |
|   {% endif %}                                        |
|                                                      |
|   [ error message, if any — generic wording ]        |
|                                                      |
|   [ Log In (spinner on submit) ]                     |
|                                                      |
|   Forgot password? -> /password-reset/               |
|   Don't have an account? Register -> /users/register/ |
+----------------------------------------------------+
```

**Form:** `method="POST" action="{% url 'login' %}"`, `{% csrf_token %}`, hidden `next` field if present, `username`, `password` (both read directly off `request.POST`, not a bound Django Form), required `role` `<select>`, conditional `captcha` field.

**Validation / error states** (see [architecture/authentication-flow.md](../architecture/authentication-flow.md) for the full flow):
- Locked account → lockout message with a wait-time estimate (same message whether the account is real or not).
- CAPTCHA required after 2 recent failures (default) → shown inline, must be solved before credentials are even checked.
- Wrong password, wrong role, or nonexistent username → identical generic "Invalid credentials" message (anti-enumeration).
- On success with 2FA owed → redirected to `/users/2fa/setup/` or `/users/2fa/verify/` before reaching the app.

**Note:** admin accounts cannot use this form (role choices are Editor/Author/Contributor/Reader only) — they authenticate at `/admin/` (see [admin.md](admin.md)).

## Register

**Template:** `templates/users/register.html`
**Route:** `/users/register/` (`users.views.register`, name=`register`)
**Users/roles:** Public/anonymous.

```text
+----------------------------------------------------+
|                  [ Register ]                        |
|                                                      |
|   {{ form.as_p }}  -- RegisterForm fields:            |
|     Username:  [......................]              |
|     Email:     [......................]              |
|     Password1: [......................]              |
|       Password strength meter: [######----] (JS-driven, advisory only) |
|     Password2 (confirm): [......................]     |
|     CAPTCHA:   [ image ]  Enter: [........]           |
|                                                      |
|   [ Register (spinner on submit) ]                    |
+----------------------------------------------------+
```

**Form:** `UserCreationForm` subclass (`RegisterForm`) — `username`, `email`, `password1`, `password2`, `captcha` (`CaptchaField`, unconditional — every registration requires CAPTCHA, unlike login's progressive threshold). New accounts default to `role="reader"` (the model default; the registration form doesn't expose a role field).

**Behavior:** on success, the user is logged in immediately (`login(request, user)`) and redirected to `/` — no email verification step exists.

**Validation:** Django's `AUTH_PASSWORD_VALIDATORS` (similarity to username, minimum length, common-password check) enforced server-side; the strength meter is purely a client-side visual aid (`password-strength.js`), not a gate.

## Password reset

**Templates:** `users/password_reset_form.html` → `password_reset_done.html` → (emailed link) → `password_reset_confirm.html` → `password_reset_complete.html`
**Routes:** `/password-reset/`, `/password-reset/done/`, `/password-reset/confirm/<uidb64>/<token>/`, `/password-reset/complete/` (all Django's built-in `auth_views`, wired in `config/urls.py`)

```text
Step 1: /password-reset/                Step 3: /password-reset/confirm/<uid>/<token>/
+---------------------------+           +---------------------------+
| Enter your email:          |           | {% if validlink %}         |
| [.......................]  |           |   New password: [......]   |
| [ Send Reset Link ]        |           |   Confirm:       [......]  |
| <- Back to Login           |           |   [ Reset Password ]       |
+---------------------------+           | {% else %}                 |
                                          |   "Link Expired"           |
Step 2: /password-reset/done/            |   -> request a new one     |
+---------------------------+           | {% endif %}                 |
| "Check your email..."      |           +---------------------------+
| <- Back to Login           |
+---------------------------+            Step 4: /password-reset/complete/
                                          +---------------------------+
                                          | "Password reset complete"  |
                                          | [ Go to Login ]            |
                                          +---------------------------+
```

Form rendering uses `django-crispy-forms` (`{{ form|crispy }}`) on the request and confirm steps, rather than the project's hand-styled form markup used elsewhere. Email is sent via `EMAIL_BACKEND` (console backend by default — prints to the server console rather than sending a real email unless configured otherwise in production).

## Cross-cutting error states

- Session-inactivity logout redirects here with a "Your session expired due to inactivity" message (`users/middleware.py`).
- Any request to a 2FA-gated URL while unverified redirects here through the 2FA pages first, not directly — see [2fa.md](2fa.md).
