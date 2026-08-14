# Architecture Documentation

Football Hub is a Django monolith (server-rendered templates + HTMX partials) with one ASGI-based real-time subsystem (Django Channels, for live chat). See [technology-stack.md](technology-stack.md) for the full confirmed dependency list.

## Contents

- [system-architecture.md](system-architecture.md) — the main high-level architecture document: presentation/application/real-time/data/external-services/static layers, with a component diagram.
- [application-architecture.md](application-architecture.md) — internal Django structure: URL routing, views, forms, services, mixins, middleware, signals, permissions, per-app breakdown.
- [security-architecture.md](security-architecture.md) — authentication, authorization (roles vs. Django Groups/Permissions), session security, application security controls, with a security flow diagram.
- [deployment-architecture.md](deployment-architecture.md) — the current Docker architecture (containers, volumes, networking), plus the original pre-Docker analysis of what's implied vs. absent (still no CI/CD), environment variables, dev-vs-prod differences. See also [docs/docker.md](../docker.md) for commands.
- [data-flow.md](data-flow.md) — six data flow diagrams: authentication, blog publishing workflow, search, live chat, Telegram announcements, feedback/subscription.
- [authentication-flow.md](authentication-flow.md) — the complete login → lockout/CAPTCHA → 2FA → session flow as a single Mermaid flowchart.
- [realtime-chat-flow.md](realtime-chat-flow.md) — Django Channels architecture in detail, with sequence diagrams for message delivery and chat closure.
- [technology-stack.md](technology-stack.md) — every confirmed technology, grouped by layer, with what's explicitly absent.

## Architecture decisions

Documented only where the codebase (comments, docstrings, or the project's own `.md` files) actually states a rationale. Where no rationale is recorded, this is stated explicitly rather than inferred.

| Decision | Rationale found in the codebase |
|---|---|
| PostgreSQL over SQLite | The implementation does not explicitly document the rationale. (`db.sqlite3` is gitignored defensively, but no comment explains why Postgres was chosen over SQLite for this project.) |
| Django Channels for live chat | The implementation does not explicitly document the rationale for choosing Channels specifically, but the *requirement* for real-time, bidirectional delivery (visitor ↔ agent messaging, live unread badges, inbox updates without polling) is evident from the feature itself — a request/response HTTP cycle can't push server-initiated updates to the browser. |
| WebSockets (vs. polling) for chat | Same as above — inferred from the feature's real-time requirements, not from an explicit comment. |
| Redis required in production for chat | **Explicitly documented** in `config/settings.py`: "Set `REDIS_URL` in production (and run more than one worker) to fan messages out across processes via channels_redis." `InMemoryChannelLayer` only routes within a single process. |
| Daphne / ASGI required | **Explicitly implied** by the presence of `config/asgi.py`'s `ProtocolTypeRouter` handling both `http` and `websocket` scopes — a pure-WSGI server cannot serve the `websocket` scope at all. Not stated as prose anywhere, but structurally unambiguous. |
| WhiteNoise for static files | The implementation does not explicitly document the rationale, but its effect (serving static files from the app process without a separate static file server) is a common, low-operational-overhead choice for a self-contained deployment. |
| TOTP (django-otp) for 2FA | The implementation does not explicitly document why TOTP specifically (vs. SMS or WebAuthn) was chosen, beyond `users/twofactor.py`'s docstring noting it's built on django-otp's existing primitives rather than a custom implementation — i.e. "use the standard library for this app framework" rather than a security-driven comparison of 2FA methods. |
| Role-based permissions (dual system: `CustomUser.role` + Django Groups) | The implementation does not explicitly document why two separate authorization mechanisms coexist. `blog/management/commands/setup_roles.py` has an inline comment explaining *one specific design choice within it* (Author's Group permissions deliberately exclude `change_post` so object-level ownership checks in the view handle per-post editing instead of a blanket permission) — but not why the `role` field and Group system exist as two parallel systems rather than one. |
| django-csp Report-Only mode (not enforced) | **Explicitly documented** in `Content Security policy Docs/CSP_NOTES.md`: the policy is being run in Report-Only mode deliberately, to observe real traffic and close known gaps (e.g. a since-removed flag-image CDN reference) before enforcing. |
| `django-csp` package instead of Django's built-in CSP middleware | **Explicitly documented** in `CSP_NOTES.md`: Django's own CSP middleware only shipped in Django 6.0; this project runs Django 5.2, so the third-party package was used instead, deliberately chosen to mirror the Django 6 settings shape for an easy future migration. |
| Lockout/CAPTCHA keyed on submitted username, not account existence | **Explicitly documented** in `users/security.py`'s module docstring: prevents the login form from being usable as a username-enumeration oracle. |
| Single-session enforcement only for privileged roles | Inferred from the code (`users/signals.py`'s docstring explains the *mechanism*, and the role set matches `TWO_FACTOR_REQUIRED_ROLES`), but no comment explicitly states *why* readers are exempt — reasonably read as "elevated-privilege accounts carry more risk if session-hijacked, so are held to a stricter single-session policy," but that inference is not stated in the code itself.

## Traceability

Major features traced from requirement/feature down to database and UI, confirming nothing here is invented.

```text
Live Chat
  |
  +--> chat app
  |
  +--> Models: ChatSession, ChatMessage
  |
  +--> Consumers: ChatConsumer, SupportInboxConsumer (chat/consumers.py)
  |
  +--> Channels/WebSockets: chat/routing.py, config/asgi.py
  |
  +--> HTTP endpoints: chat/views.py (start_chat, chat_messages, close_chat,
  |     support_inbox, support_chat_room)
  |
  +--> UI: components/chat_widget.html (visitor), chat/support_inbox.html,
        chat/support_room.html (staff)

Editorial Workflow (draft -> review -> approved -> published)
  |
  +--> blog app
  |
  +--> Model: Post.status, Post.is_approved, Post.is_published,
  |     Post.editor_feedback, Post.status_changed_at, Post.published_at
  |
  +--> Views: blog/views/posts.py (post_submit_for_review, post_request_changes,
  |     post_approve, post_publish, post_withdraw_from_review)
  |
  +--> Permissions: blog.add_post, blog.can_approve_post, blog.can_publish_post
  |     (Django Group/Permission system, blog/management/commands/setup_roles.py)
  |
  +--> UI: blog/author_dashboard.html, blog/editor_dashboard.html + their
        HTMX-refreshed partials

Two-Factor Authentication
  |
  +--> users app
  |
  +--> Models: django_otp's TOTPDevice, StaticDevice, StaticToken (third-party,
  |     not project-defined)
  |
  +--> Policy: users/twofactor.py (who's required, enrollment/verification rules)
  |
  +--> Enforcement: users/middleware.py: TwoFactorEnforcementMiddleware
  |
  +--> Views: users/views.py (two_factor_setup, two_factor_verify,
  |     two_factor_disable, two_factor_regenerate_codes)
  |
  +--> UI: users/two_factor_setup.html, two_factor_verify.html,
        two_factor_recovery_codes.html

Login Lockout & CAPTCHA
  |
  +--> users app
  |
  +--> Model: LoginAttempt (audit trail; lockout state is derived, not stored)
  |
  +--> Policy: users/security.py
  |
  +--> Views: users/views.py: login_view, users/forms.py:
  |     LockoutAwareAdminAuthenticationForm (covers /admin/ too)
  |
  +--> UI: users/login.html (conditional CAPTCHA field), templates/admin/login.html

Telegram Announcements
  |
  +--> blog app
  |
  +--> Trigger: blog/views/posts.py: post_publish only
  |
  +--> Service: blog/services/telegram.py: send_new_post_announcement
  |
  +--> External API: Telegram Bot API (python-telegram-bot)
  |
  +--> Persisted result: Post.telegram_announced_at
  |
  +--> UI: blog/partials/author_dashboard_lists.html,
        blog/partials/editor_dashboard_lists.html (announcement status shown per post)

Support Inbox / Notifications (chat unread + in-app Notification model)
  |
  +--> chat app (unread chat badge) + blog app (in-app Notification model)
  |
  +--> Models: ChatMessage.is_read, blog.Notification
  |
  +--> Services: chat/services.py: get_unread_count
  |
  +--> Context processors: chat/context_processors.py: unread_chat_count
  |
  +--> UI: components/masthead.html (badge), blog/author_dashboard.html /
        editor_dashboard.html (notification list, marked read on dashboard open)
```

## Accuracy methodology

Every diagram and claim in this architecture documentation was produced by reading the actual source files (models, views, urls, middleware, settings, consumers, templates, static JS) rather than inferring from filenames or conventions — including re-running `python manage.py check` for this task and cross-checking the project's own prior audit documents (`SECURITY_AUDIT_2026-08-10.md`, `Content Security policy Docs/CSP_NOTES.md`, `TELEGRAM.md`, `TESTING.md`) against the current code, which surfaced at least one place those documents are now stale (a `flagcdn.com`/`match_block.html` reference in `CSP_NOTES.md` that no longer exists in the current homepage service or templates — see [Issues discovered] in the top-level project report for this task).
