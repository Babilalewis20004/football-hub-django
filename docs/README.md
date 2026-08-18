# Football Hub — Software Design Documentation

This documentation describes the **actual current implementation** of the Football Hub Django project, produced by reading the source code directly (models, views, URLs, forms, middleware, signals, services, consumers, templates, static assets, and settings) rather than from feature intent or filenames. Where something couldn't be confirmed from the code, it's marked "Not determinable from the current codebase" rather than assumed.

Football Hub is a Django 5.2 monolith: server-rendered templates + Bootstrap 5 + a small amount of HTMX, one real-time subsystem (Django Channels, for live chat), and a single PostgreSQL database. It is **not** a live football-data platform — there is no fixtures/scores/standings feature; "Champions League," "La Liga," etc. in the navbar are editorial content categories, not live sports data. See [architecture/system-architecture.md](architecture/system-architecture.md) for the full picture.

## Contents

### System design
- [architecture/README.md](architecture/README.md) — architecture documentation index, plus architecture decisions and feature traceability
- [architecture/system-architecture.md](architecture/system-architecture.md) — high-level component diagram and layer-by-layer explanation
- [architecture/application-architecture.md](architecture/application-architecture.md) — internal Django structure: routing, views, forms, services, middleware, per-app breakdown
- [architecture/security-architecture.md](architecture/security-architecture.md) — authentication, authorization, session security, application security controls
- [architecture/deployment-architecture.md](architecture/deployment-architecture.md) — implied production topology, environment variables, dev-vs-prod differences, and current Docker setup
- [security.md](security.md) — DevSecOps pipeline: SAST, dependency/secret/container scanning, PR gating, and how to run the same scans locally
- [architecture/data-flow.md](architecture/data-flow.md) — six data flow diagrams covering auth, publishing, search, chat, Telegram, feedback/subscription
- [architecture/authentication-flow.md](architecture/authentication-flow.md) — the complete login → lockout/CAPTCHA → 2FA → session flowchart
- [architecture/realtime-chat-flow.md](architecture/realtime-chat-flow.md) — Django Channels architecture with sequence diagrams
- [architecture/technology-stack.md](architecture/technology-stack.md) — every confirmed technology in use, grouped by layer

### Database design
- [database/README.md](database/README.md) — database documentation index
- [database/erd.md](database/erd.md) — Entity-Relationship Diagram (Mermaid)
- [database/schema.md](database/schema.md) — full field-by-field table definitions and migration history
- [database/relationships.md](database/relationships.md) — FK delete behavior, M2M relationships, unique constraints, cascade risks
- [database/data-dictionary.md](database/data-dictionary.md) — flat field reference across all models

### UI wireframes
- [wireframes/README.md](wireframes/README.md) — wireframes index, global layout, and confirmed dead/orphaned frontend code
- [wireframes/home-page.md](wireframes/home-page.md), [authentication.md](wireframes/authentication.md), [blog.md](wireframes/blog.md), [post-detail.md](wireframes/post-detail.md), [search.md](wireframes/search.md), [profile.md](wireframes/profile.md), [comments.md](wireframes/comments.md), [live-chat.md](wireframes/live-chat.md), [support-inbox.md](wireframes/support-inbox.md), [notifications.md](wireframes/notifications.md), [2fa.md](wireframes/2fa.md), [feedback.md](wireframes/feedback.md), [admin.md](wireframes/admin.md)

### Existing project documentation (preserved, not duplicated here)
- [../SECURITY_AUDIT_2026-08-10.md](../SECURITY_AUDIT_2026-08-10.md) — dependency vulnerability audit and Django deployment-check findings
- [../TELEGRAM.md](../TELEGRAM.md) — Telegram announcement integration setup/behavior
- [../TESTING.md](../TESTING.md) — pytest setup and test-coverage backlog
- [../Content Security policy Docs/CSP_NOTES.md](../Content%20Security%20policy%20Docs/CSP_NOTES.md) — CSP Report-Only rollout plan and directive rationale
- [../Content Security policy Docs/CSP_BROWSER_TESTING.md](../Content%20Security%20policy%20Docs/CSP_BROWSER_TESTING.md) — CSP browser verification walkthrough

## Issues discovered during this documentation effort

Recorded here because they were surfaced by cross-checking the codebase against itself and against the project's own prior documentation — not invented, and not fixed as part of this documentation-only task.

| # | Finding | Where |
|---|---|---|
| 1 | *(Resolved.)* At the time, `CustomUser.role` and the Django Group/Permission system (created by `setup_roles`) were two separate mechanisms with no code path that assigned a user to their matching Group automatically. `users.signals.sync_role_group` (a `post_save` signal on `CustomUser`) now keeps them in sync on every role change, and `manage.py backfill_user_roles` repairs any pre-existing account whose Group membership had drifted from its `role`. | `users/signals.py`, `users/management/commands/backfill_user_roles.py` |
| 2 | *(Resolved.)* At the time, the "Contributor" Django Group had no corresponding `CustomUser.role` value (`role` choices were only `admin`/`editor`/`author`/`reader`). `contributor` is now a full `ROLE_CHOICES` value, assignable through the Django admin's role selector and usable to log in via the public `/login/` form. | `users/models.py: CustomUser.ROLE_CHOICES`, `users/admin.py`, `users/views.py: PUBLIC_LOGIN_ROLES` |
| 3 | `Post.category` is `on_delete=CASCADE` — deleting a `Category` from Django admin deletes every post in it, including published, live content, with no confirmation specific to that consequence. | `blog/models/post.py` |
| 4 | `Post.author` is `on_delete=CASCADE` — a user deleting their own account (`delete_account`, self-service) silently deletes every post they've ever authored, including published content, with only a password-confirmation step (no warning about post deletion specifically). | `blog/models/post.py`, `users/views.py: delete_account` |
| 5 | `blog/views/comments.py: delete_comment` is fully implemented (with a correct ownership check) but has no URL registered and no template links to it — unreachable in the running application. | `blog/urls.py`, `blog/views/comments.py`, `templates/blog/post_detail.html` |
| 6 | `blog/services/search.py: search_posts_queryset` duplicates logic that `blog/views/search.py` re-implements inline instead of calling — dead code, not a second search path. | `blog/services/search.py`, `blog/views/search.py` |
| 7 | Several template components are defined but never included by any live page: `article_grid.html` (references a `worldcup_posts` variable no view ever sets — implies an unbuilt "World Cup" content section), `bullet_links.html`, `featured_article.html`, `news_feed.html`, `components/sidebar.html`, `blog/includes/sidebar.html` (a second, also-unused sidebar), `slider.html` (+ its JS/CSS), `pagination.html`. | `templates/components/`, `templates/blog/includes/` |
| 8 | Footer "Quick Links" (News/About/Contact) and "Latest News" links (Match Reports/Transfer News/Player Interviews/Match Predictions/**League Standings**) are dead `href="#"` placeholders. "League Standings" implies a feature with zero backend support anywhere in the codebase. The homepage CTA band's "Get notified" button is also a dead link, not wired to the working `/subscribe/` endpoint the footer newsletter form *does* use correctly. | `templates/components/footer.html`, `templates/components/cta_band.html` |
| 9 | `post_detail.html` has a status-badge branch for a `"pending"` value that isn't part of `Post.status`'s actual choices (`draft`/`in_review`/`needs_changes`/`approved`/`published`) — likely dead conditional code. | `templates/blog/post_detail.html` |
| 10 | *(Partially resolved since this table was written.)* At the time, no `Procfile`, deployment script, Dockerfile, or CI/CD configuration existed. A `Dockerfile` + Compose setup now exists (see [architecture/deployment-architecture.md](architecture/deployment-architecture.md)) and resolves the production start command and media-serving gap via Nginx. A CI/CD **security** pipeline now exists (`.github/workflows/security.yml`, see [security.md](security.md)) — but it's scanning/testing only, not deployment automation; there is still no automated build/push/deploy job. | Confirmed by filesystem search; also flagged independently in `SECURITY_AUDIT_2026-08-10.md` §8 |
| 11 | `Content Security policy Docs/CSP_NOTES.md` references `blog/services/homepage.py:22-23` hardcoding flag images from `https://flagcdn.com` and a `templates/components/match_block.html` template — **neither exists in the current codebase** (confirmed by direct file read and project-wide grep). This project document is stale relative to the current code; this documentation package reflects the actual current state (no flag images, no match-block feature), not that document's snapshot. | `Content Security policy Docs/CSP_NOTES.md` vs. current `blog/services/homepage.py` |
| 12 | CKEditor 4 (bundled by `django-ckeditor`) is end-of-life with unfixed security issues — confirmed by re-running `python manage.py check` for this task, still the one warning present. | `manage.py check` output |
| 13 | CSP is deployed in Report-Only mode only, not yet enforced (by design, per `CSP_NOTES.md`'s own rollout plan — not treated as a defect here, just recorded for completeness). | `config/settings.py: CONTENT_SECURITY_POLICY_REPORT_ONLY` |

None of these were altered — this was a documentation task only; no application code was modified.

## Validation performed

```text
python manage.py check   → 1 warning (ckeditor.W001, pre-existing, informational — see issue #12 above), 0 errors
python -m pytest -v      → 134 passed in 697.4s, 0 failed
```

Both were run against the project's existing configuration with no code changes made.
