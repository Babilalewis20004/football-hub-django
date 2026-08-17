# Testing

## Pytest setup

This project runs its existing Django `TestCase` suite through `pytest` via `pytest-django`, alongside (not instead of) `python manage.py test`.

- Packages: `pytest==9.1.1`, `pytest-django==4.14.0`, `pytest-cov==7.1.0` (see `requirements.txt`)
- Config: [pytest.ini](pytest.ini) — sets `DJANGO_SETTINGS_MODULE = config.settings` and test discovery for `tests.py`, `test_*.py`, `*_tests.py`
- Run the suite: `python -m pytest -v`
- Run with coverage: `python -m pytest --cov --cov-report=term-missing`

As of the last run, both runners agree on **231 tests**, all passing.

## Current coverage status (whole project)

Last measured with `python -m pytest --cov --cov-report=term-missing`:

**Overall: 99% (3050 statements, 41 missed)**

Every app/service/view module is at 100% except the handful below, all of which are minor edge cases rather than unexercised features:

| File | Coverage | What's left |
|---|---|---|
| `blog/views/posts.py` | 92% | Scattered permission/edge-case branches in the CRUD + editorial workflow views (largest remaining gap by line count) |
| `blog/models/bookmark.py` | 92% | One line |
| `blog/models/notification.py` | 89% | One line |
| `users/security.py` | 94% | A few lines |
| `users/middleware.py` | 94% | Session-timeout edge case |
| `users/models.py` | 90% | Two lines |
| `users/views.py` | 99% | One line — see below |
| `blog/views/home.py`, `blog/views/search.py`, `blog/forms.py`, `config/settings.py`, `config/urls.py`, `pages/models.py`, `pages/views.py`, `blog/migrations/0015...` | 87-98% | One line each |

**`users/views.py:327`** is the one line worth calling out specifically: it's a fallback inside `_totp_throttle_message()` for when `django_otp`'s `verify_is_allowed()` returns a not-allowed result *without* a `locked_until` key. Reading `django_otp.models.ThrottlingMixin.verify_is_allowed()` directly confirms it always includes `locked_until` in that case today — so this line is defensive code guarding against a `django_otp` behavior change, not a reachable path in the current dependency version. Forcing it would mean mocking a third-party library's internals to produce a shape it doesn't actually produce; not worth it for one line.

## End-of-Project Test Coverage Backlog — CLOSED

> This backlog (tracked here and duplicated in `SECURITY_AUDIT_2026-08-10.md` §4) is now closed. Coverage went from 83% (`blog` app only, 129 statements missed) to 99% (whole project, 41 missed) and every previously-tracked gap was resolved. Kept below for history instead of deleted, since it records *why* things ended up the way they did.

| File | Coverage before | Resolution |
|---|---|---|
| `blog/services/comments.py` | 17% | Tested — `create_comment()` unit test + `post_detail` POST integration test |
| `blog/views/interactions.py` | 43% | Tested — like/bookmark toggling, permission checks |
| `blog/views/taxonomy.py` | untested | Tested — author/category/tag listing filters |
| `blog/sitemaps.py` | untested | Tested — sitemap classes + `/sitemap.xml` endpoint |
| `chat/views.py`, `chat/permissions.py` | untested (no test file existed) | Tested — new `chat/tests.py` |
| `config/views.py` | untested (no test file existed) | Tested — new `config/tests.py` |
| `pages/views.py` | untested (no test file existed) | Tested — `pages/tests.py` filled in |
| `blog/models/category.py` | 67% | Tested — slug auto-generation and the collision retry loop |
| `blog/views/dashboard.py` | 78% | Tested — `saved_posts()` had no test at all; now covered |
| `blog/services/telegram.py` | 81% | Tested — not-configured, success, and `TelegramError` paths, all mocked at `_send_message` (not `asyncio.run`, which left dangling un-awaited coroutines and a `RuntimeWarning`) |
| `users/views.py` | 85% | Tested — `next`-redirect branches in `login_view`, the captcha-failure-that-also-locks-out combination, `profile` POST (valid + invalid), `delete_account`, the "already enrolled" `two_factor_setup` redirect, the OTP-throttled `two_factor_verify` path, `two_factor_regenerate_codes` when 2FA isn't enabled |
| `blog/views/comments.py` (`delete_comment`) | 0%, not wired to any URL | **Resolved by wiring it up**, not by testing dead code. `docs/wireframes/comments.md` had already flagged this as a real functional gap (working ownership-check logic, just never registered) and explicitly recommended wiring it in — so it's now registered at `comment/<pk>/delete/` in `blog/urls.py`, with a "Delete" button added to `post_detail.html` for a comment's own author, and tested in `blog/tests/test_comments.py` |
| `blog/mixins.py` (`AuthorRequiredMixin`) | 0%, unused | **Resolved by deletion.** `docs/architecture/application-architecture.md` already documented it as unused by any view, and every view in this project is function-based (no CBVs exist to attach a `dispatch()` mixin to) — unlike `delete_comment`, there was no real gap here to close, just orphaned code. Deleted rather than tested; docs updated to match |

### Checklist

- [x] Test `blog/services/comments.py`
- [x] Test `blog/views/interactions.py`
- [x] Test `blog/views/taxonomy.py`
- [x] Test `blog/sitemaps.py`
- [x] Test `chat/views.py` and `chat/permissions.py`
- [x] Test `config/views.py`
- [x] Test `pages/views.py`
- [x] Resolve `blog/views/comments.py` — wired up `delete_comment` and tested it
- [x] Resolve `blog/mixins.py` — confirmed genuinely dead, deleted
- [x] Improve coverage for `blog/models/category.py` (slug collision loop)
- [x] Improve coverage for `blog/views/dashboard.py`
- [x] Improve coverage for `blog/services/telegram.py`
- [x] Improve coverage for `users/views.py`
- [x] Run the complete pytest suite (`python -m pytest -v`) — 231 passed
- [x] Run coverage with `--cov --cov-report=term-missing`
- [x] Review all remaining uncovered statements — all are minor edge cases or (one line) defensive code for a third-party invariant
- [x] Confirm no important production code remains unintentionally untested
- [x] Target at least 90% overall coverage if practical — currently at 99%
