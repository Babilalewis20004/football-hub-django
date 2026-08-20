# Security Architecture

This is the most heavily engineered part of the codebase. Every control documented here is traced to a specific file.

## Security flow diagram

```mermaid
flowchart TD
    Start(["User submits login form"]) --> Lockout{"Account locked?<br/>(users.security.check_lockout)"}
    Lockout -- "Yes" --> LockedMsg["Show lockout message<br/>(generic, same for real/unreal usernames)"]
    Lockout -- "No" --> Captcha{"Recent failure streak<br/>>= LOGIN_CAPTCHA_AFTER_ATTEMPTS?"}
    Captcha -- "Yes" --> CaptchaCheck{"CAPTCHA valid?"}
    CaptchaCheck -- "No" --> RecordFail1["Record failed attempt<br/>(reason=captcha_failed)"] --> Lockout
    CaptchaCheck -- "Yes" --> RoleCheck
    Captcha -- "No" --> RoleCheck{"role in<br/>(editor, author, reader)?"}
    RoleCheck -- "No" --> RecordFail2["Record failed attempt<br/>(reason=invalid_role)"] --> GenericError["Generic 'Invalid credentials'"]
    RoleCheck -- "Yes" --> Authn{"authenticate()<br/>succeeds AND<br/>user.role == submitted role?"}
    Authn -- "No" --> RecordFail3["Record failed attempt<br/>(reason=invalid_credentials/role_mismatch)"] --> GenericError
    Authn -- "Yes" --> RecordSuccess["Record successful attempt"] --> DjangoLogin["django.contrib.auth.login()"]
    DjangoLogin --> SingleSession["users.signals.enforce_single_session<br/>(evicts other sessions if role is admin/editor/author)"]
    SingleSession --> Gate{"users.twofactor.two_factor_gate(user)"}
    Gate -- "'setup' (role requires 2FA, none enrolled)" --> Setup["/2fa/setup/ — QR enrollment"]
    Gate -- "'verify' (device confirmed, any role)" --> Verify["/2fa/verify/ — TOTP or recovery code"]
    Gate -- "None" --> Session["Authenticated session established"]
    Setup --> Verify2["otp_login() on confirmation"] --> Session
    Verify --> Session
    Session --> PermCheck{"Django permission /<br/>role check per view"}
    PermCheck --> App["Django application response"]
```

## Authentication

### Username/password authentication
Standard Django `authenticate()`/`login()` (`django.contrib.auth`), backed by `CustomUser` (`AUTH_USER_MODEL = 'users.CustomUser'`). Passwords are stored using Django's default hasher chain (PBKDF2-SHA256 first).

**Unusual, load-bearing detail:** the public login form (`templates/users/login.html`) requires the user to additionally select a **role** (`Editor`/`Author`/`Reader`) from a dropdown. `users/views.py: login_view` rejects the attempt — with the same generic error as a wrong password — if `user.role != role`. This means a valid password alone is not sufficient; the submitted role must also match the account's actual role. `admin` accounts are excluded from `PUBLIC_LOGIN_ROLES` entirely and must authenticate through `/admin/` instead.

### Login attempt tracking & account lockout
`users/security.py` + `users/models.py: LoginAttempt`. Every attempt (success or failure, real or nonexistent username) is recorded. Lockout state is *derived* from the most recent `LOGIN_MAX_FAILED_ATTEMPTS` (default 5) rows for a username, not stored as a counter — if all of them are failures and the latest is within `LOGIN_LOCKOUT_MINUTES` (default 2), the account is locked. A successful attempt anywhere in that window breaks the streak.

**Deliberate design choice:** lockout is keyed on the *submitted username string*, not on whether it maps to a real account, and the lockout/CAPTCHA/error responses are identical either way — this prevents the login form from being usable to enumerate valid usernames.

### CAPTCHA
`django-simple-captcha`. Progressive: once a username's recent failure streak reaches `LOGIN_CAPTCHA_AFTER_ATTEMPTS` (default 2, must stay below the lockout threshold), the next attempt must include a solved CAPTCHA, checked *before* credentials. Applied identically to:
- The public login form (`LoginCaptchaForm` in `users/forms.py`).
- Registration (`RegisterForm` includes a `CaptchaField` unconditionally).
- The Django admin login (`LockoutAwareAdminAuthenticationForm`, installed via `admin.site.login_form = ...` in `users/admin.py`) — so `/admin/` cannot be used to bypass lockout/CAPTCHA.

### TOTP two-factor authentication (django-otp)
`users/twofactor.py`, `users/views.py`. Built entirely on `django_otp.plugins.otp_totp` (TOTP devices) and `otp_static` (recovery codes) — no custom cryptography.

- **Mandatory** for `admin`, `editor`, `author` roles (`TWO_FACTOR_REQUIRED_ROLES`). These roles are redirected to `/2fa/setup/` before they can do anything else, enforced both immediately after login (`login_view`) and on every subsequent request (`TwoFactorEnforcementMiddleware`, covering the `/admin/` login path too, which bypasses `login_view` entirely).
- **Optional** for `reader` accounts, self-service via the profile page.
- Enrollment: a QR code (`otpauth://` URL rendered via `qrcode`, embedded as a `data:image/png;base64,...` URI — this is why `img-src` in the CSP allows `data:`) plus a manual base32 key fallback. A device is created unconfirmed and flips to confirmed only once the user proves a valid code.
- **10 recovery codes** are generated at enrollment (and on-demand regeneration), shown exactly once in plaintext, backed by `otp_static.StaticDevice`/`StaticToken`. Regenerating invalidates all previous codes.
- Login-time verification (`/2fa/verify/`) accepts either a live TOTP code or an unused recovery code, both throttled with django-otp's built-in exponential backoff (`device.verify_is_allowed()`).
- Privileged roles cannot self-service-disable 2FA (`two_factor_disable` explicitly blocks it); only an admin can reset a user's enrollment (Django admin action `reset_two_factor_enrollment`, calls `reset_2fa_for_user`).
- `OTP_ADMIN_HIDE_SENSITIVE_DATA = True` hides raw TOTP secrets/recovery codes in Django admin, even from superusers browsing the device list.

### Session management
- Sessions are DB-backed (Django's default `django.contrib.sessions.backends.db`).
- `SessionInactivityTimeoutMiddleware` (`users/middleware.py`) stamps a `last_activity` timestamp into the session on every authenticated request; if more than `SESSION_INACTIVITY_TIMEOUT` seconds (default 300 = 5 minutes) have passed, it force-logs-out the user and shows an explanatory message — rather than letting the session silently expire at the storage layer.
- `SESSION_COOKIE_AGE = SESSION_INACTIVITY_TIMEOUT` and `SESSION_SAVE_EVERY_REQUEST = True` provide a *backstop* at the storage layer with the same window, in case the middleware is ever bypassed.
- `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`.
- **Single-session enforcement for privileged roles**: `users/signals.py: enforce_single_session`, hooked to Django's `user_logged_in` signal (so it applies no matter which login path is used, including `/admin/`). For `admin`/`editor`/`author` accounts, a fresh login deletes every other active `django_session` row belonging to that user (found by decoding each session's `_auth_user_id`, since the `Session` model has no user FK). `reader` accounts may stay logged in on multiple devices simultaneously.
- `SESSION_COOKIE_HTTPONLY = True`.

### Logout
`POST`-only (`@require_POST`), `@login_required`, at `/logout/` (`users.views.logout_view`) — calls `django.contrib.auth.logout()` and logs the event. Also reachable from within the 2FA setup/verify pages ("Log out instead") for a user stuck mid-flow.

## Authorization

Two authorization mechanisms, now kept in sync by `users/signals.py: sync_role_group` (see below — this was previously a known gap; it has since been fixed):

### 1. `CustomUser.role` (application-level role field)
A plain string field — one of `admin`/`editor`/`author`/`contributor`/`reader` (`CustomUser.ROLE_CHOICES`) — checked directly in code for: which login roles are selectable, which roles require 2FA, which roles get single-session enforcement, which roles can act as chat support agents, and object-level post-editing rules. `role` defaults to `"reader"` at the model level, so every newly registered account (`users/forms.py: RegisterForm`, which deliberately has no `role` field for a public user to submit) starts as a Reader.

### 2. Django Groups & Permissions (`blog/management/commands/setup_roles.py`)
A `manage.py setup_roles`-driven system that creates five Django `Group`s — **Admin, Editor, Author, Contributor, Reader** — and assigns `Permission` rows to each. This is the system Django's own permission checks (`request.user.has_perm(...)`, `@permission_required` in `blog/views/posts.py`) actually resolve against for a non-superuser:

| Group | Permissions granted |
|---|---|
| Admin | All permissions on the `Post` content type (add/change/delete/view + `can_publish_post`/`can_feature_post`/`can_approve_post`) |
| Editor | `add_post`, `change_post`, `delete_post`, `view_post`, `can_publish_post`, `can_feature_post`, `can_approve_post` |
| Author | `add_post`, `view_post` only — **deliberately excludes `change_post`** (a code comment explains: that permission is checked globally, not per-object, so granting it would let any author edit every other author's posts; authors edit their own posts via an object-level ownership check in `post_update` instead, which needs no permission) |
| Contributor | `add_post`, `view_post` (same as Author) |
| Reader | `view_post` only |

### Editorial action matrix

The table above lists raw Django permission codenames; this is the same authorization mapped onto the actual actions available in `blog/views/posts.py`, including two ownership-gated actions (`post_submit_for_review`, `post_withdraw_from_review`) that have no Django `Permission` at all — they're checked purely by `post.author == request.user`, so any role that can create posts can submit/withdraw their own, regardless of Group.

| Role | Create Articles | Edit Own Articles | Edit Others' Articles | Submit for Review | Withdraw from Review | Approve / Request Changes | Publish | Delete |
|---|---|---|---|---|---|---|---|---|
| **Admin** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Editor** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Author** | ✅ | ✅¹ | ❌ | ✅² | ✅² | ❌ | ❌ | ❌ |
| **Contributor** | ✅ | ✅¹ | ❌ | ✅² | ✅² | ❌ | ❌ | ❌ |
| **Reader** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

¹ Own post only, and only while it's still `draft` or `needs_changes` — the author loses edit access to their own post the moment it's `published` (`post_update`, `blog/views/posts.py:131-133`). Admin/Editor are exempt from this: holding `blog.change_post` skips both the ownership check *and* the published-state check (line 120-121), so they can edit any post in any state, including already-published ones.
² Own post only (`post.author == request.user`); "Submit for review" requires status `draft`/`needs_changes`, "Withdraw" requires `in_review` (`blog/views/posts.py:246`, `273`).

Two behaviors worth calling out because they're easy to assume otherwise:
- There is no "Reject" action or status — a post an Editor/Admin sends back is `needs_changes` (`post_request_changes`), and the author resubmits it through the same `post_submit_for_review` action, not a separate re-draft step.
- `post_publish` (`blog/views/posts.py:163-188`) does not require the post to already be `approved` — it only checks the `blog.can_publish_post` permission. An Editor/Admin can publish a post straight out of `draft` or `in_review`, skipping the approval step entirely.

### Keeping the two in sync: `users/signals.py: sync_role_group`
A `post_save` signal on `CustomUser` that runs whenever `role` actually changes (new user, or an existing user's `role` was edited) and calls `apply_role_group()`: it adds the user to the one Group matching their new `role` and removes them from the other four application-role Groups, so a role change can never leave a user holding two roles' worth of Group permissions at once (e.g. still in "Editor" after being demoted to "Reader"). The mapping itself (`ROLE_GROUP_NAMES`) is derived directly from `CustomUser.ROLE_CHOICES` rather than duplicated, since the choice labels (Admin/Editor/Author/Contributor/Reader) already match the Group names exactly.

`apply_role_group()` is also reused by `manage.py backfill_user_roles` (see below) to repair any account whose Group membership drifted from its `role` field before this signal existed, without duplicating the add/remove logic a second time.

### Default Reader assignment and legacy accounts
- **New registrations:** `role` defaults to `"reader"` at the model level, and `RegisterForm.Meta.fields` doesn't include `role` — so nothing in `request.POST` can ever set it, even a deliberately crafted extra `role=admin` field. Django `ModelForm`s only ever populate fields listed in `Meta.fields`; anything else in the POST body is silently ignored.
- **Existing/legacy accounts:** `manage.py backfill_user_roles` (`users/management/commands/backfill_user_roles.py`) resets any account whose `role` value isn't one of `ROLE_CHOICES` to `"reader"` — never any other role — and, separately, repairs Group membership for accounts whose `role` is already valid but whose Groups never got synced to it. It's idempotent and wired into `docker/entrypoint.sh` right after `setup_roles`, so it runs automatically on every deploy rather than needing a manual shell command.

### Root cause of the "Admin shown as Reader" bug
`users/migrations/0002_customuser_role.py` added the `role` column with `default='reader'` via `AddField` — which, per Django's migration semantics, backfills that default onto **every existing row**, including any superuser created via `createsuperuser` *before* that migration ran. `createsuperuser` only ever sets `is_superuser`/`is_staff`/the username/password — it doesn't know about this project's custom `role` field, so it was never set explicitly either. The result: an account that's a genuine Django superuser (`is_superuser=True`, full DB/admin access) can have `role="reader"`, and anything reading `user.role` (the masthead's admin-only UI, `TWO_FACTOR_REQUIRED_ROLES`, `SINGLE_SESSION_ROLES`, `chat.permissions.SUPPORT_ROLES`, `PUBLIC_LOGIN_ROLES`) sees "Reader", not "Admin".

### Relationship between Django superuser, `is_staff`, and the application Admin role
These are three genuinely independent flags/values, and this project does **not** collapse them into one another automatically:

- **`is_superuser`** — Django's own "bypass every permission check" flag. Only ever set explicitly (`createsuperuser`, or by another superuser in Django admin).
- **`is_staff`** — required to log into `/admin/` at all. Also only ever set explicitly.
- **Application `role="admin"`** — this project's own concept, checked directly in `user.role`-based code paths (2FA requirement, single-session eviction, chat support-agent access, the masthead's admin-only UI) and, via `sync_role_group`, in the "Admin" Django Group's `Post` permissions.

Nothing in this codebase sets any one of these from the others — a superuser is not automatically given `role="admin"`, and setting `role="admin"` does not grant `is_staff`/`is_superuser`. This is deliberate: `manage.py backfill_user_roles` and the Django-admin role selector both intentionally avoid ever promoting an account to the application Admin role on their own (see "Protecting the Admin role" below) — only a human with shell/superuser access decides that, the same existing mechanism the test fixtures already use (`role="admin", is_staff=True`, set together by hand). Because Django admin's user-management screens require the `users.change_customuser`/`users.view_customuser` permissions — which no application-role Group grants — only a superuser (who bypasses permission checks entirely) can currently reach the role-management UI in practice, regardless of what `role` value a staff account happens to hold.

### Protecting the Admin role in the Django admin UI
`users/admin.py: CustomUserAdmin.get_form` strips `"admin"` out of the `role` dropdown's choices for any request user that isn't a Django superuser, leaving Reader/Contributor/Author/Editor as the only selectable values. A superuser still sees the full choice list — that's the one remaining path to grant the Admin role through the UI, consistent with it already being the only role that requires deliberate, out-of-band setup (`is_staff`/`is_superuser`) alongside it.

### Role summary table

| Role | 2FA | Single-session | Public login option | Can create posts | Can approve/publish | Chat support agent |
|---|---|---|---|---|---|---|
| Admin | Mandatory | Yes | No (uses `/admin/`) | Yes (via Group) | Yes (via Group) | Yes |
| Editor | Mandatory | Yes | Yes | Yes (via Group) | Yes (via Group) | Yes |
| Author | Mandatory | Yes | Yes | Yes (via Group) | No | No |
| Contributor | Optional (self-service) | No | Yes | Yes (via Group) | No | No |
| Reader | Optional (self-service) | No | Yes | No | No | No |

## Application security

| Control | Setting/mechanism | Notes |
|---|---|---|
| CSRF protection | `django.middleware.csrf.CsrfViewMiddleware`, `CSRF_COOKIE_HTTPONLY = True` | Standard Django CSRF tokens in every form; HTMX requests get the token injected via a global `htmx:configRequest` listener reading the `<meta name="csrf-token">` tag. The `/csp-report/` endpoint is explicitly `@csrf_exempt` because browsers POST CSP reports without a token. |
| XSS protection | Django template auto-escaping (default) + `nh3.clean()` sanitization of `Post.content` server-side (`blog/forms.py`) | CKEditor sanitizes client-side only; server-side sanitization guards against a request that bypasses the browser entirely. Comment content is not explicitly sanitized but is rendered without `\|safe`, relying on Django's default auto-escaping. |
| SQL injection protection | Django ORM exclusively — no raw SQL found anywhere in the codebase | Search/homepage/taxonomy views build querysets with `Q()` objects, never string-interpolated SQL |
| Clickjacking | `X_FRAME_OPTIONS = 'DENY'`, `django.middleware.clickjacking.XFrameOptionsMiddleware`, plus CSP `frame-ancestors 'none'` (belt-and-suspenders) | |
| MIME sniffing | `SECURE_CONTENT_TYPE_NOSNIFF = True` | |
| Referrer leakage | `SECURE_REFERRER_POLICY = 'same-origin'` | |
| HTTPS enforcement | `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS` — **all environment-driven, all default to off/0** | Intended to be turned on via env vars once HTTPS is confirmed in front of the app in production; currently disabled by default (correct for local HTTP dev, but must be explicitly enabled per environment — nothing in the codebase forces this) |
| Content Security Policy | `django-csp` 4.0, **Report-Only mode** (`CONTENT_SECURITY_POLICY_REPORT_ONLY`, not the enforcing `CONTENT_SECURITY_POLICY` setting) | Violations logged to `logs/csp_violations.log` via `/csp-report/`, not yet blocking anything. See `Content Security policy Docs/CSP_NOTES.md` for the full directive-by-directive rationale and the documented pre-enforcement checklist. Nonce-based (`request.csp_nonce`) for the project's own inline `<script>` blocks; `'unsafe-inline'` is required for `style-src` specifically because of CKEditor 4's runtime inline styling, per that document. |
| Password hashing | Django's default hasher chain (PBKDF2-SHA256) | Reused for admin, chat, and account-deletion password-confirmation checks (`user.check_password(...)`) throughout `users/views.py` |
| Password strength validation | `AUTH_PASSWORD_VALIDATORS`: `UserAttributeSimilarityValidator`, `MinimumLengthValidator`, `CommonPasswordValidator` | Server-side; a separate client-side JS meter (`password-strength.js`) on the registration page is advisory only, not enforced |
| Open-redirect protection | `users.security.safe_next_url()` / `django.utils.http.url_has_allowed_host_and_scheme()` | Applied to every `?next=` parameter across login, 2FA, and newsletter-subscribe redirect flows |
| Security event logging | `security` logger → `logs/security.log` | Records lockouts, failed logins (public and admin), CAPTCHA failures, unauthorized edit attempts, 2FA failures/successes, account-deletion failures |

## Known gaps (from the codebase and existing project docs — not invented)

- CSP is Report-Only, not enforced (see `CSP_NOTES.md`).
- CKEditor 4 is end-of-life with unfixed security issues (`ckeditor.W001`, confirmed by re-running `python manage.py check` for this documentation task).
- HTTPS-related settings default to off and must be explicitly enabled per environment at deploy time.
