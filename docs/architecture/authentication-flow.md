# Authentication Flow

Full detail behind the summary in [security-architecture.md](security-architecture.md). Traced from `users/views.py`, `users/security.py`, `users/twofactor.py`, `users/middleware.py`, `users/signals.py`, and `users/forms.py`.

## Complete flowchart

```mermaid
flowchart TD
    A(["User opens /login/"]) --> B["Submits username, password, role"]
    B --> C{"check_lockout(username)"}
    C -- "Locked" --> D["record_attempt(reason=locked_out)<br/>Show lockout message<br/>(same wording regardless of whether<br/>the username is real)"]
    D --> B
    C -- "Not locked" --> E{"requires_captcha(username)?<br/>(failure streak >= LOGIN_CAPTCHA_AFTER_ATTEMPTS)"}
    E -- "Yes" --> F{"CAPTCHA valid?"}
    F -- "No" --> G["record_attempt(reason=captcha_failed)<br/>Re-check lockout (may have just tripped)"]
    G --> C
    F -- "Yes" --> H
    E -- "No" --> H{"role in (editor, author, contributor, reader)?"}
    H -- "No" --> I["record_attempt(reason=invalid_role)<br/>Generic 'Invalid credentials'"]
    I --> B
    H -- "Yes" --> J["authenticate(username, password)"]
    J --> K{"user found AND<br/>user.role == submitted role?"}
    K -- "No" --> L["record_attempt(reason=invalid_credentials<br/>or role_mismatch)<br/>Generic 'Invalid credentials'<br/>(re-check lockout immediately)"]
    L --> B
    K -- "Yes" --> M["record_attempt(successful=True)<br/>django.contrib.auth.login(request, user)"]
    M --> N["enforce_single_session signal handler:<br/>if role in {admin, editor, author},<br/>delete every other active Session row<br/>belonging to this user"]
    N --> O{"two_factor_gate(user)"}
    O -- "'setup'<br/>(role requires 2FA, none enrolled yet)" --> P["Redirect to /2fa/setup/"]
    O -- "'verify'<br/>(a confirmed TOTP device exists)" --> Q["Redirect to /2fa/verify/"]
    O -- "None<br/>(reader, no 2FA opted in)" --> R["Redirect to safe `next` or home"]
    P --> S["Scan QR / enter manual key<br/>Submit 6-digit code"]
    S --> T{"device.verify_token(code)?"}
    T -- "No" --> S
    T -- "Yes" --> U["Device confirmed<br/>Old unconfirmed devices cleaned up<br/>10 recovery codes generated + shown once<br/>otp_login(request, device)"]
    U --> R
    Q --> V["Enter TOTP code or recovery code"]
    V --> W{"Throttled?<br/>(device.verify_is_allowed())"}
    W -- "Yes" --> X["Show wait-time message"]
    X --> V
    W -- "No" --> Y{"Valid TOTP code?"}
    Y -- "Yes" --> Z["otp_login(request, device)"]
    Y -- "No" --> AA{"Valid unused recovery code?"}
    AA -- "Yes" --> AB["otp_login(request, recovery_device)<br/>Warn: N codes remaining"]
    AA -- "No" --> AC["Invalid code error"]
    AC --> V
    Z --> R
    AB --> R
    R --> AD(["Fully authenticated, OTP-verified session"])
    AD --> AE["Every subsequent request:<br/>SessionInactivityTimeoutMiddleware checks<br/>elapsed time since last_activity"]
    AE --> AF{">SESSION_INACTIVITY_TIMEOUT<br/>(default 300s)?"}
    AF -- "Yes" --> AG["Force logout()<br/>'Session expired due to inactivity' message"]
    AF -- "No" --> AH["Refresh last_activity timestamp<br/>Continue request"]
    AD --> AI["Every subsequent request:<br/>TwoFactorEnforcementMiddleware"]
    AI --> AJ{"Gate still 'setup' or<br/>'verify' AND not is_verified()?"}
    AJ -- "Yes" --> AK["Redirect back to the owed 2FA step<br/>(covers /admin/ logins and bookmarked URLs<br/>that bypass login_view)"]
    AJ -- "No" --> AL["Request proceeds normally"]
    AD --> AM["User clicks Logout<br/>(POST /logout/, login_required)"]
    AM --> AN["django.contrib.auth.logout()<br/>Redirect home"]
```

## Key behaviors worth calling out explicitly

- **The lockout/CAPTCHA/error responses are indistinguishable for real vs. nonexistent usernames.** This is a deliberate anti-enumeration measure (see code comments in `users/security.py`), not an oversight — a penetration tester should expect this and not flag it as a bug.
- **Role selection is a genuine authorization input, not decoration.** Because `login_view` compares the submitted `role` against `user.role`, a correct password with the wrong role selected fails exactly like a wrong password. `admin` is deliberately not one of the selectable options here - admin accounts authenticate through the separate `/admin/` login form instead (see below).
- **The `/admin/` login path is a separate code path** (`users/forms.py: LockoutAwareAdminAuthenticationForm`, installed via `users.admin: admin.site.login_form = ...`) that duplicates the lockout/CAPTCHA logic against the same `LoginAttempt` table, but does **not** duplicate the role-matching check (Django admin login only checks `is_staff`). It is covered by `enforce_single_session` (via the shared `user_logged_in` signal) and by `TwoFactorEnforcementMiddleware` (which runs on every request regardless of login path), but not by `login_view`'s own post-login redirect logic.
- **2FA verification state lives on the session** (`django_otp`'s `is_verified()`), separate from Django's own `is_authenticated`. A user can be `is_authenticated=True` but not yet `is_verified()` — that gap is exactly what `TwoFactorEnforcementMiddleware` closes on every request, not just immediately after login.
- **Recovery codes are single-use and finite.** `two_factor_verify` decrements availability implicitly (each `StaticToken` is deleted/consumed by django-otp on successful use — standard django-otp behavior); the UI warns the user with a remaining-count message when they're used.

## Where this is enforced (file map)

| Step | File |
|---|---|
| Lockout / CAPTCHA policy | `users/security.py` |
| Login view logic | `users/views.py: login_view` |
| Admin login form override | `users/forms.py: LockoutAwareAdminAuthenticationForm`, `users/admin.py` |
| Single-session eviction | `users/signals.py: enforce_single_session` |
| 2FA policy (who/when) | `users/twofactor.py` |
| 2FA views (setup/verify/disable/regenerate) | `users/views.py` |
| Session inactivity timeout | `users/middleware.py: SessionInactivityTimeoutMiddleware` |
| 2FA enforcement backstop | `users/middleware.py: TwoFactorEnforcementMiddleware` |
| Middleware ordering | `config/settings.py: MIDDLEWARE` (both custom middlewares run after `django_otp.middleware.OTPMiddleware`, which populates `request.user.is_verified()`) |
