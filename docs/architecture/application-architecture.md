# Application Architecture

This document describes the internal structure of the Django project: how a request moves from URL to response, and how the four apps (`users`, `blog`, `chat`, `pages`) are organized internally.

## Request flow (typical HTTP page)

```text
Browser
   |
   v
config/urls.py  (root URLconf)
   |
   +--> admin/                  --> django.contrib.admin (customized login form)
   +--> csp-report/             --> config.views.csp_report_view
   +--> sitemap.xml, robots.txt --> config.views / blog.sitemaps
   +--> ''  (blog.urls)         --> blog app
   +--> users/  (users.urls)    --> users app
   +--> chat/   (chat.urls)     --> chat app
   +--> ''  (pages.urls)        --> pages app
   +--> captcha/                --> django-simple-captcha
   +--> login/, logout/, password-reset/* --> users.views / django.contrib.auth views
   |
   v
View function (all views in this project are function-based — no CBVs
except pages/views.py's TemplateView subclasses and Django's built-in
auth views for password reset)
   |
   +---- Form validation (django.forms.ModelForm / Form subclasses)
   |
   +---- Service layer call (blog/services/*.py) for non-trivial business logic
   |
   +---- Permission check (@login_required, @permission_required,
   |      or an inline `request.user.role`/`has_perm` check)
   |
   v
Django ORM (model methods, querysets)
   |
   v
PostgreSQL
   |
   v
Template render (templates/<app>/*.html, extending base.html)
   |
   v
HTTP Response --> Browser
```

## App-by-app breakdown

### `users` — authentication & account management

| Layer | Files |
|---|---|
| Models | `users/models.py` — `CustomUser`, `LoginAttempt` |
| Forms | `users/forms.py` — `RegisterForm`, `LoginCaptchaForm`, `TwoFactorCodeForm`, `ProfileUpdateForm`, `LockoutAwareAdminAuthenticationForm` |
| Views | `users/views.py` — `register`, `login_view`, `logout_view`, `profile`, `delete_account`, `two_factor_setup`, `two_factor_verify`, `two_factor_disable`, `two_factor_regenerate_codes` (all function-based) |
| URLs | `users/urls.py` (mounted at `/users/`) + two routes (`login`, `logout`) registered directly in `config/urls.py` at the site root |
| Services/policy modules | `users/security.py` (lockout + CAPTCHA policy, IP extraction, safe-redirect validation), `users/twofactor.py` (2FA enrollment/verification policy on top of django-otp) |
| Middleware | `users/middleware.py` — `SessionInactivityTimeoutMiddleware`, `TwoFactorEnforcementMiddleware` |
| Signals | `users/signals.py` — `enforce_single_session`, hooked to `django.contrib.auth.signals.user_logged_in` |
| Admin | `users/admin.py` — custom `CustomUserAdmin` (2FA columns/action), read-only `LoginAttemptAdmin`, and a global `admin.site.login_form` override to apply lockout/CAPTCHA to `/admin/` too |

### `blog` — content, editorial workflow, engagement

| Layer | Files |
|---|---|
| Models | `blog/models/` split into `category.py`, `post.py`, `comment.py`, `bookmark.py`, `notification.py`, re-exported via `blog/models/__init__.py` |
| Forms | `blog/forms.py` — `PostForm` (with server-side content sanitization), `CommentForm` |
| Views | Split by concern under `blog/views/`: `home.py` (homepage), `posts.py` (CRUD + editorial workflow + dashboards), `interactions.py` (like/bookmark, HTMX partial responses), `search.py`, `taxonomy.py` (author/category/tag listing pages), `dashboard.py` (generic user dashboard + saved posts), `comments.py` (`delete_comment` — ownership-checked comment deletion, wired to `blog/urls.py`) |
| Services | `blog/services/posts.py` (`can_view_post`, `get_related_posts`), `blog/services/homepage.py` (`get_homepage_context`), `blog/services/comments.py` (`create_comment`), `blog/services/telegram.py` (`send_new_post_announcement`), `blog/services/search.py` (`search_posts_queryset` — defined but **not called by any view**; `blog/views/search.py` duplicates the same query logic inline instead) |
| URLs | `blog/urls.py`, mounted at the site root (`''`) in `config/urls.py` |
| Context processors | `blog/context_processors.py` — `sidebar_data` (categories/trending/latest — feeds the orphaned `blog/includes/sidebar.html`, which no template currently includes), `seo_defaults` (canonical URL, site name) |
| Management commands | `blog/management/commands/setup_roles.py` — creates/refreshes the `Admin`/`Editor`/`Author`/`Contributor`/`Reader` Django Groups and their permissions; `users/management/commands/backfill_user_roles.py` — resets any `CustomUser` with an unrecognized `role` to `reader` and repairs Group membership drift for the rest. Both are idempotent and run automatically on every container start (`docker/entrypoint.sh`), not just once at setup time. |
| Sitemaps | `blog/sitemaps.py` — `PostSitemap`, `CategorySitemap`, `StaticViewSitemap`, wired into `config/urls.py`'s `sitemap.xml` |
| Admin | `blog/admin.py` — plain `admin.site.register()` for `Category`, `Post`, `Comment`, `Bookmark` (no custom `ModelAdmin` classes) |

### `chat` — live chat & support inbox

| Layer | Files |
|---|---|
| Models | `chat/models.py` — `ChatSession`, `ChatMessage` |
| Views (HTTP) | `chat/views.py` — `start_chat`, `chat_messages`, `close_chat` (visitor-facing, JSON), `support_inbox`, `support_chat_room` (staff-facing, HTML) |
| Consumers (WebSocket) | `chat/consumers.py` — `ChatConsumer` (one instance per `ChatSession`, shared by visitor and assigned staff), `SupportInboxConsumer` (live feed of new sessions/messages across all open chats for staff) |
| Routing | `chat/routing.py` — `websocket_urlpatterns`, included from `config/asgi.py` |
| Permissions | `chat/permissions.py` — `is_support_agent(user)`, `support_agent_required` decorator |
| Services | `chat/services.py` — `get_unread_count()` |
| Context processor | `chat/context_processors.py` — `unread_chat_count` (feeds the support-inbox badge in the navbar, only for support agents) |
| URLs | `chat/urls.py`, mounted at `/chat/` |
| Admin | `chat/admin.py` — `ChatSessionAdmin` (with an inline read-only `ChatMessage` list), `ChatMessageAdmin` |

### `pages` — static content & lightweight forms

| Layer | Files |
|---|---|
| Models | `pages/models.py` — `Feedback`, `Subscriber` |
| Forms | `pages/forms.py` — `FeedbackForm`, `SubscribeForm` |
| Views | `pages/views.py` — six `TemplateView` subclasses for static pages (`PrivacyPolicyView`, `TermsOfUseView`, `AboutUsView`, `CookiesView`, `CareersView`, `ContactUsView`) plus two function views (`feedback_view`, `subscribe_view`) |
| URLs | `pages/urls.py`, mounted at the site root (`''`) alongside `blog.urls` |
| Admin | `pages/admin.py` — `FeedbackAdmin`, `SubscriberAdmin` |

## Cross-app interaction

- `blog` depends on `users` only through `settings.AUTH_USER_MODEL` (every FK to a user goes through the string reference, per Django convention) — no direct Python imports of `users` models into `blog`.
- `chat` depends on `users` the same way (FKs) and reads `CustomUser.role` directly (`chat/models.py: SUPPORT_ROLES`, `chat/permissions.py`) to determine staff status — this is the one place role logic is duplicated outside the `users` app rather than imported from it.
- `pages` depends on `users` only through the optional `Feedback.user` FK.
- `config` (the project package) ties everything together: `config/urls.py` includes each app's URLconf, `config/settings.py` registers all four apps plus third-party apps, `config/asgi.py` wires in `chat.routing`, and `config/views.py` hosts two small site-wide views (`csp_report_view`, `robots_txt`) that don't belong to any single app.

## Permissions and decorators actually used

| Mechanism | Where | Purpose |
|---|---|---|
| `@login_required` | Most authenticated-only views across `users`/`blog`/`chat` | Redirects anonymous users to `LOGIN_URL` |
| `@permission_required("blog.<codename>", raise_exception=True)` | `blog/views/posts.py` (`post_create`, `post_publish`, `post_approve`, `editor_dashboard`, `author_dashboard`, etc.) | Enforces Django's `Group`/`Permission` system (see [security-architecture.md](security-architecture.md)) |
| `@require_POST` / `@require_GET` | Many state-changing or JSON-only views across all four apps | Rejects the wrong HTTP method (405) |
| Inline `request.user.role` / `request.user.has_perm(...)` checks | `blog/views/posts.py: post_update` (object-level "own post" check), `chat/permissions.py: is_support_agent` | Object-level authorization that Django's permission system doesn't express on its own |
| `chat.permissions.support_agent_required` | `chat/views.py: support_inbox`, `support_chat_room` | Combines `@login_required` with a role check, raising `PermissionDenied` (403) otherwise |

## Static assets

- `STATICFILES_DIRS = [BASE_DIR / 'static']` (source) and `STATIC_ROOT = BASE_DIR / 'staticfiles'` (collected, via `collectstatic`) — served by WhiteNoise in all environments.
- CSS is organized into `static/css/core/` (variables, layout, global resets, theme, animations, utilities), `static/css/components/` (one file per reusable UI component), and `static/css/pages/` (one file per page type).
- JS is flat under `static/js/`, one file per interactive feature (see [technology-stack.md](technology-stack.md) and [realtime-chat-flow.md](realtime-chat-flow.md)).
