# Admin

**Route:** `/admin/` — Django's default admin site (`django.contrib.admin`), with one custom template override.
**Users/roles:** `is_staff=True` accounts only (Django's own admin gate — separate from, but often overlapping with, `CustomUser.role == 'admin'`).

## Admin Login

**Template:** `templates/admin/login.html` (overrides Django's built-in `admin/login.html`)

```text
+----------------------------------------------------+
|              Django administration                   |
|                                                      |
|  Username: [......................]                 |
|  Password: [......................]                 |
|                                                      |
|  {% if form.captcha %}                                |
|  CAPTCHA: [ image ]  Enter: [........]                |
|  {% endif %}                                          |
|                                                      |
|  {% if user.is_authenticated %}                        |
|    "You are authenticated as X, but not authorized     |
|     to access this page. Would you like to login       |
|     to a different account?"                            |
|  {% endif %}                                            |
|                                                      |
|  [ Log in ]                                            |
+----------------------------------------------------+
```

**Form:** `LockoutAwareAdminAuthenticationForm` (`users/forms.py`), installed via `admin.site.login_form = LockoutAwareAdminAuthenticationForm` (`users/admin.py`) — applies the exact same failed-attempt lockout and progressive-CAPTCHA policy as the public `/login/` form, sharing the same `LoginAttempt` table (see [architecture/security-architecture.md](../architecture/security-architecture.md)).

**What this form does not do:** unlike the public login view, it does not check a submitted "role" against `CustomUser.role` — admin login is gated purely by Django's own `is_staff`/`is_superuser` checks.

**Note:** the template references a `{% url 'admin_password_reset' as ... %}` tag for a URL name that isn't defined anywhere in this project's URLconfs. Because it's used with the `as` form, this fails silently and the associated block is simply skipped — inherited as-is from Django's own default admin login template, not a project-specific bug.

## Admin Site (post-login)

Standard Django admin, with these registered models and customizations confirmed in the codebase:

| App | Model | Customization |
|---|---|---|
| `users` | `CustomUser` | `CustomUserAdmin(UserAdmin)` — adds `role` column/filter plus two computed columns, "2FA enabled" (`has_2fa_enabled`) and "2FA required" (`requires_2fa`); adds a "Reset 2FA enrollment for selected users" bulk action |
| `users` | `LoginAttempt` | Read-only (`has_add_permission`/`has_change_permission` return `False`); list/filter/search on `username`, `successful`, `reason`, `ip_address`, `timestamp` |
| `blog` | `Category`, `Post`, `Comment`, `Bookmark` | Plain `admin.site.register()` — default Django admin UI, no custom `ModelAdmin` classes, no custom list displays/filters |
| `chat` | `ChatSession` | `ChatSessionAdmin` — list display incl. status/agent/timestamps, inline read-only `ChatMessage` list |
| `chat` | `ChatMessage` | `ChatMessageAdmin` — list display, filter by `is_staff_message` |
| `pages` | `Feedback` | `FeedbackAdmin` — filterable by rating/date, searchable |
| `pages` | `Subscriber` | `SubscriberAdmin` — searchable by email |

**Also registered indirectly by third-party apps** (not this project's own admin.py files, but visible in the admin site since those apps are in `INSTALLED_APPS`): `Group`/`Permission` (`django.contrib.auth`), `TOTPDevice` (`django_otp.plugins.otp_totp`, with `OTP_ADMIN_HIDE_SENSITIVE_DATA = True` hiding raw secrets), `StaticDevice`/`StaticToken` (`django_otp.plugins.otp_static`, same secret-hiding setting).

**Notification** (`blog.Notification`) is **not registered in Django admin at all** — there's no `admin.py` registration for it anywhere in `blog/admin.py`, so notification rows are only visible through the dashboards that generate/consume them, or direct database access.

## Not part of this project's own templates

Every other admin page (model list views, change forms, the dashboard/index page) uses Django's stock admin templates unmodified — only `admin/login.html` has a project-specific override.
