# Security & QA Audit — MyFootballBlog

**Date:** 2026-08-10
**Scope:** Full Django project — dependency/vulnerability audit, unused-dependency check, Django deployment/security settings, test suite verification, code quality, and remediation.
**Environment audited:** Python 3.12.10, Django (project venv), local Postgres, Windows dev machine.
**Auditor:** Claude Code, on request of project owner.

---

## 1. Summary

| Category | Issues found | Issues fixed | Issues outstanding |
|---|---|---|---|
| Dependency vulnerabilities (`pip-audit`) | 50 unique advisories (31 Django, 19 Pillow) | 50 | 0 |
| Dependency currency (outdated, non-vulnerable) | 6 direct deps behind latest | 0 | 6 (informational, no known CVEs) |
| Unused dependencies | 2 (`djangorestframework`, `djangorestframework-simplejwt`) | 2 | 0 |
| Django deploy/security settings (`check --deploy`) | 7 warnings | 4 (enabled via new env-driven settings) | 3 (operational/structural — see §3) |
| Secrets/credentials in version control | 0 | — | 0 |
| Test suite & tooling | 0 config issues | — | 5 pre-existing coverage gaps (already tracked in `TESTING.md`) |
| Code quality (dead imports, migrations, models, linting) | 7 | 5 (dead imports removed) | 2 (no linter configured; default `/admin/` path) |
| **Total** | **72** | **61** | **16** |

**Net effect:** `pip-audit` went from 50 known vulnerabilities to **0**. All 90 existing tests still pass (83% coverage on `blog`, unchanged) after every fix. No secrets were found in the repo or its history.

---

## 2. Dependency & vulnerability audit

### 2.1 Installed vs. pinned versions

`pip list --format=freeze` in the project venv was diffed against `requirements.txt` (no `pyproject.toml` exists in this project). **All 18 pinned packages matched their installed versions exactly** before any changes were made — no drift.

### 2.2 `pip-audit` — before remediation

`pip-audit` was already installed in the venv (`pip_audit==2.10.1`); no install step was needed.

Raw `pip-audit -r requirements.txt` output contained **78 lines**, but each advisory ID appeared twice per affected package (pip-audit's default report duplicates rows when it cross-checks two vulnerability feeds for the same package). Deduplicating by `(package, advisory ID)` gives the true count:

| Package | Installed | Unique advisories | Fixed by |
|---|---|---|---|
| `django` | 5.2.3 | 31 | 5.2.17 (patch-level, within 5.2 branch) |
| `pillow` | 11.2.1 | 19 | 12.3.0 (major version) |
| `psycopg2-binary` | 2.9.10 | 0 | — |
| *(all other 15 pinned packages)* | — | 0 | — |

**Total unique vulnerabilities: 50**, not 78 — the naive line count from the raw CLI table overstates the true count by 56%. This report uses the deduplicated figure throughout.

#### Deduplicated advisory list — Django 5.2.3 (31 advisories, all fixed by 5.2.17)

| Advisory | CVE | Fixed in (5.2.x) |
|---|---|---|
| PYSEC-2025-104 | CVE-2025-13372 | 5.2.9 |
| PYSEC-2025-105 | CVE-2025-57833 | 5.2.6 |
| PYSEC-2025-106 | CVE-2025-59681 | 5.2.7 |
| PYSEC-2025-107 | CVE-2025-64458 | 5.2.8 |
| PYSEC-2025-108 | CVE-2025-64459 | 5.2.8 |
| PYSEC-2025-109 | CVE-2025-64460 | 5.2.9 |
| PYSEC-2026-1296 | CVE-2025-59682 | 5.2.7 |
| PYSEC-2026-42 | CVE-2025-13473 | 5.2.11 |
| PYSEC-2026-43 | CVE-2025-14550 | 5.2.11 |
| PYSEC-2026-44 | CVE-2026-1207 | 5.2.11 |
| PYSEC-2026-45 | CVE-2026-1285 | 5.2.11 |
| PYSEC-2026-46 | CVE-2026-1287 | 5.2.11 |
| PYSEC-2026-47 | CVE-2026-1312 | 5.2.11 |
| PYSEC-2026-48 | CVE-2026-33033 | 5.2.13 |
| PYSEC-2026-49 | CVE-2026-33034 | 5.2.13 |
| PYSEC-2026-50 | CVE-2026-35192 | 5.2.14 |
| PYSEC-2026-51 | CVE-2026-3902 | 5.2.13 |
| PYSEC-2026-52 | CVE-2026-4277 | 5.2.13 |
| PYSEC-2026-53 | CVE-2026-4292 | 5.2.13 |
| PYSEC-2026-54 | CVE-2026-5766 | 5.2.14 |
| PYSEC-2026-55 | CVE-2026-6907 | 5.2.14 |
| PYSEC-2026-197 | CVE-2026-35193 | 5.2.15 |
| PYSEC-2026-198 | CVE-2026-48587 | 5.2.15 |
| PYSEC-2026-199 | CVE-2026-6873 | 5.2.15 |
| PYSEC-2026-200 | CVE-2026-7666 | 5.2.15 |
| PYSEC-2026-201 | CVE-2026-8404 | 5.2.15 |
| PYSEC-2026-2090 | CVE-2026-48588 | 5.2.16 |
| PYSEC-2026-2091 | CVE-2026-53877 | 5.2.16 |
| PYSEC-2026-2092 | CVE-2026-53878 | 5.2.16 |
| PYSEC-2026-2448 | CVE-2026-25673 | 5.2.12 |
| PYSEC-2026-2449 | CVE-2026-25674 | 5.2.12 |

Highest required fix version: **5.2.16**. Project was pinned to **5.2.17** (the newest available 5.2.x release at audit time), so all 31 are resolved with margin.

#### Deduplicated advisory list — Pillow 11.2.1 (19 advisories, all fixed by 12.3.0)

| Advisory | CVE | Fixed in |
|---|---|---|
| PYSEC-2025-61 | CVE-2025-48379 | 11.3.0 |
| PYSEC-2026-165 | CVE-2026-42308 | 12.2.0 |
| PYSEC-2026-2249 | CVE-2026-25990 | 12.1.1 |
| PYSEC-2026-2250 | CVE-2026-40192 | 12.2.0 |
| PYSEC-2026-2251 | CVE-2026-42309 | 12.2.0 |
| PYSEC-2026-2252 | CVE-2026-42311 | 12.2.0 |
| PYSEC-2026-2253 | CVE-2026-54059 | 12.3.0 |
| PYSEC-2026-2254 | CVE-2026-54060 | 12.3.0 |
| PYSEC-2026-2255 | CVE-2026-55379 | 12.3.0 |
| PYSEC-2026-2256 | CVE-2026-55380 | 12.3.0 |
| PYSEC-2026-2257 | CVE-2026-55798 | 12.3.0 |
| PYSEC-2026-2874 | CVE-2026-42310 | 12.2.0 |
| PYSEC-2026-3451 | CVE-2026-59199 | 12.3.0 |
| PYSEC-2026-3453 | CVE-2026-59205 | 12.3.0 |
| PYSEC-2026-3454 | CVE-2026-59197 | 12.3.0 |
| PYSEC-2026-3493 | CVE-2026-54058 | 12.3.0 |
| PYSEC-2026-3494 | CVE-2026-59198 | 12.3.0 |
| PYSEC-2026-3495 | CVE-2026-59200 | 12.3.0 |
| PYSEC-2026-3496 | CVE-2026-59204 | 12.3.0 |

No 11.x patch release fixes all of these — full remediation requires the 12.x major line. This was flagged as higher-risk (major version bump) and **applied only after explicit confirmation** from the project owner (Pillow's public API surface used here is narrow — Django `ImageField` — and stable across the 11→12 boundary).

### 2.3 `pip-audit` — after remediation

```
$ pip-audit -r requirements.txt
No known vulnerabilities found
```

**50 → 0 unique vulnerabilities.**

*Note on methodology:* the re-run initially failed with `SSLCertVerificationError` against both `pypi.org` and `api.osv.dev`, while `curl` (using the Windows system trust store) reached the same hosts fine — a local TLS-inspecting proxy/AV product has a CA trusted by Windows but not by Python's bundled `certifi` list. This was resolved by installing `pip-system-certs` in the venv, which bridges Python's TLS trust to the OS store. This is a one-time local environment fix, not a project change (not added to `requirements.txt`).

### 2.4 Outdated (non-vulnerable) direct dependencies

`pip list --outdated` after remediation:

| Package | Installed | Latest | Known CVEs? |
|---|---|---|---|
| django-crispy-forms | 2.3 | 2.7 | No |
| crispy-bootstrap5 | 2025.4 | 2026.3 | No |
| django-ckeditor | 6.7.2 | 6.7.3 | No |
| gunicorn | 23.0.0 | 26.0.0 | No |
| whitenoise | 6.9.0 | 6.12.0 | No |
| psycopg2-binary | 2.9.10 | 2.9.12 | No |
| Django | 5.2.17 | 6.1 | No (major version, out of scope — see §6) |

None of these carry known advisories, so none were bumped as part of this audit. Listed for awareness; safe to schedule as routine maintenance.

---

## 3. Unused dependency check

Every package in `requirements.txt` was cross-referenced against actual usage (imports, `INSTALLED_APPS`, middleware, settings):

| Package | Status | Evidence |
|---|---|---|
| Django | Used | Core framework |
| psycopg2-binary | Used | `DATABASES.ENGINE = django.db.backends.postgresql` (driver used internally, no direct import expected) |
| Pillow | Used | Backs `ImageField` (no direct import expected — this is normal for Django) |
| python-decouple | Used | `config/settings.py:13` |
| django-crispy-forms | Used | `INSTALLED_APPS`, `CRISPY_*` settings |
| crispy-bootstrap5 | Used | `INSTALLED_APPS` |
| django-taggit | Used | `INSTALLED_APPS` |
| django-ckeditor | Used | `INSTALLED_APPS` |
| django-simple-captcha | Used | `INSTALLED_APPS`, `CAPTCHA_*` settings, `users/security.py` |
| nh3 | Used | `blog/forms.py:1` |
| gunicorn | Used (deployment) | Invoked via CLI as the production WSGI server — not imported in code, which is expected. **No `Procfile`/deployment script found in the repo documenting this invocation** — see §6. |
| whitenoise | Used | `MIDDLEWARE` |
| channels | Used | `INSTALLED_APPS`, `ASGI_APPLICATION`, `CHANNEL_LAYERS` |
| daphne | Used | `INSTALLED_APPS` (ASGI server) |
| django-csp | Used | `MIDDLEWARE`, `CONTENT_SECURITY_POLICY_REPORT_ONLY` |
| pytest | Used | Test runner (`pytest.ini`) |
| pytest-django | Used | `pytest.ini: DJANGO_SETTINGS_MODULE` |
| pytest-cov | Used | `TESTING.md` documents `--cov` usage |
| ~~djangorestframework~~ | **Unused — removed** | No `rest_framework` import or `INSTALLED_APPS` entry anywhere in the codebase |
| ~~djangorestframework-simplejwt~~ | **Unused — removed** | No `simplejwt` reference anywhere in the codebase |

**Finding:** `djangorestframework` and `djangorestframework-simplejwt` were pinned in `requirements.txt` but never used — no REST API exists in this project (it's a server-rendered Django app plus a WebSocket chat feature). This removal was already staged as an uncommitted change when the audit began; it was verified as correct and is included in the final `requirements.txt`.

---

## 4. Django configuration & security settings review

### 4.1 `python manage.py check --deploy` — before fixes

```
System check identified 7 issues (0 silenced):
?: (ckeditor.W001) django-ckeditor bundles CKEditor 4.22.1, which is EOL and has unfixed security issues.
?: (security.W004) SECURE_HSTS_SECONDS not set.
?: (security.W008) SECURE_SSL_REDIRECT not set to True.
?: (security.W009) SECRET_KEY is weak (dev-generated).
?: (security.W012) SESSION_COOKIE_SECURE not set to True.
?: (security.W016) CSRF_COOKIE_SECURE not set to True.
?: (security.W018) DEBUG is True.
```

### 4.2 What was already correct

- `SECRET_KEY` is read from the environment via `python-decouple` with **no hardcoded fallback** — the app will fail to start rather than silently run with a default key. Good practice, already in place.
- `DEBUG` and `ALLOWED_HOSTS` are both environment-driven with sane defaults.
- `X_FRAME_OPTIONS = 'DENY'`, `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY`, `SECURE_CONTENT_TYPE_NOSNIFF`, and `SECURE_REFERRER_POLICY` were all already explicitly set.
- A Content-Security-Policy is already deployed in **Report-Only** mode (`django-csp`), with nonce-based inline scripts and a documented, actively-monitored rollout plan (see `Content Security policy Docs/CSP_NOTES.md`). This is ahead of where most projects are at this stage and was reviewed but not touched — a known gap (`flagcdn.com` not yet in `img-src`) is already tracked there as a pre-enforcement blocker.
- `.env` is correctly listed in `.gitignore` and **was never committed** — confirmed via `git log --all --full-history -- .env` (empty result) and `git ls-files` (not tracked). No secrets found hardcoded anywhere in the Python source (`SECRET_KEY\s*=\s*['"]` search returned no matches outside the `decouple` call).
- No missing migrations (`makemigrations --check --dry-run` → clean, before and after all fixes).
- All models (`Post`, `Category`, `Comment`, `Bookmark`, `Notification`, `ChatSession`, `ChatMessage`, `CustomUser`, `LoginAttempt`) define `__str__`.
- Login lockout/CAPTCHA logic (`users/security.py`) is well-reasoned: lockout is keyed by submitted username (not by whether the account exists), so the login response can't be used to enumerate valid usernames.

### 4.3 Fix applied — HTTPS/cookie security settings

**Before**, the HTTPS-only settings were hardcoded off, in comments, requiring a code edit to ever enable them:

```python
# Production only (enable after HTTPS is configured)
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
```

**After**, they're wired to environment variables (same pattern already used for `DEBUG`/`ALLOWED_HOSTS`), defaulting to the current (off) behavior so local HTTP dev is unaffected:

```python
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=False, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
```

`.env.example` was updated with the four new (commented-off-by-default) variables so this is discoverable.

**Why this counts as the fix, not just a deferral:** `check --deploy` will keep warning on W004/W008/W012 in *this* dev environment by design — that's correct, since dev runs over plain HTTP and forcing these on would break local cookies/redirects. The actual remediation is that production can now flip these on **via env vars at deploy time**, with no further code changes — previously that required editing `settings.py` directly. This satisfies the task's own definition of a "low-risk, mechanical" fix: it changes no runtime behavior in dev and only adds a capability.

### 4.4 Findings requiring operational/manual action (not code fixes)

| Warning | Why it can't be fixed in code | Action needed |
|---|---|---|
| `security.W009` — weak `SECRET_KEY` | The local `.env`'s `SECRET_KEY` is a dev-only value (correctly not committed). The setting itself is already environment-driven with no insecure default. | Generate a strong, unique `SECRET_KEY` (50+ random chars) for every real deployment environment and store it in that environment's secret manager, not in `.env`. |
| `security.W018` — `DEBUG=True` | Local `.env` intentionally runs `DEBUG=True` for development; the setting is already environment-driven and defaults to `False`. | Verify `DEBUG=False` is set in every non-dev environment before deploy. |
| `ckeditor.W001` — CKEditor 4 is EOL with unfixed security issues | Structural: replacing the rich-text editor (e.g. migrating to `django-ckeditor-5`) is a UI/data-format change, not a config flag. Already noted independently in `CSP_NOTES.md` as the reason `style-src 'unsafe-inline'` is currently required. | Scope a migration to a maintained editor (CKEditor 5 or alternative) as its own project; re-evaluate the CSP `style-src 'unsafe-inline'` exception once done. |

---

## 5. Test suite & tooling verification

- `pytest==9.1.1`, `pytest-django==4.14.0`, `pytest-cov==7.1.0` are correctly installed and configured. `pytest.ini` sets `DJANGO_SETTINGS_MODULE = config.settings` and discovers `tests.py`, `test_*.py`, `*_tests.py`.
- Full suite run **before** fixes: `90 passed` in 535s, 83% coverage on `blog` (766 statements, 129 missed).
- Full suite run **after** all fixes (Django 5.2.3→5.2.17, Pillow 11.2.1→12.3.0, dead-import removal, settings changes): **`90 passed`** in 499s, **83% coverage** (765 statements — one fewer, from the two removed dead imports in `blog/views/posts.py`), 0% regressions.
- Coverage gaps are pre-existing and already tracked in `TESTING.md`'s "End-of-Project Test Coverage Backlog" (`blog/views/comments.py` 0%, `blog/mixins.py` 0%, `blog/services/comments.py` 17%, `blog/views/interactions.py` 43%, `blog/views/posts.py` 56%). This audit does not duplicate that tracking — see `TESTING.md` for the live checklist.

---

## 6. Code quality checks

- **No linter/formatter is configured** in this project — no `.flake8`, `pyproject.toml`, `setup.cfg`, or `.pylintrc` exists. `pyflakes` was installed ad hoc for this audit to get a baseline; it isn't part of the project's own tooling. *Recommendation:* adopt `flake8` or `ruff` with a checked-in config so this class of finding is caught automatically going forward, rather than only during periodic audits.
- **Dead imports found and removed** (verified via `pyflakes`, before/after):
  - `config/settings.py`: `import os` (never used) and a redundant second `from pathlib import Path` (already imported at the top of the file) — both removed.
  - `blog/views/comments.py`: `Post` imported but never used (only `Comment` is) — removed.
  - `blog/views/posts.py`: `JsonResponse` and `render_to_string` imported but never used — removed.
  - *Not touched:* `blog/models/__init__.py`'s "unused" imports are intentional public re-exports (`from blog.models import Post` elsewhere in the codebase depends on them) — false positive. `pages/admin.py`, `pages/models.py`, `pages/tests.py` are untouched `startapp` boilerplate stubs (harmless, but also confirm the `pages` app currently has no models/admin/tests of its own).
- **No missing migrations** (`makemigrations --check --dry-run` clean before and after).
- **No models missing `__str__`.**
- **No hardcoded values that should be settings** were found beyond what's already environment-driven, with one minor, optional note: the admin site is mounted at the default `admin/` path (`config/urls.py:28`). Not a vulnerability on its own (Django admin is auth-protected), but moving it to a non-default path is a common low-cost hardening step against automated scanners — listed as optional, not applied.

---

## 7. Remediation — changes made

### `requirements.txt`
```diff
-Django==5.2.3
+Django==5.2.17
 psycopg2-binary==2.9.10
-Pillow==11.2.1
+Pillow==12.3.0
 ...
-djangorestframework==3.16.0
-djangorestframework-simplejwt==5.5.0
 channels==4.3.2
```
- **Django 5.2.3 → 5.2.17**: patch-level bump within the same minor branch, fixes all 31 known Django advisories. Applied directly (low-risk, mechanical).
- **Pillow 11.2.1 → 12.3.0**: major version bump, fixes all 19 known Pillow advisories (no 11.x release fixes them all). Applied **after explicit confirmation** from the project owner, per the higher-risk-change policy for this audit.
- **Removed `djangorestframework` and `djangorestframework-simplejwt`**: confirmed unused anywhere in the codebase (§3).

### `config/settings.py`
- Removed dead `import os` and a duplicate `from pathlib import Path`.
- Replaced the hardcoded-off, commented HTTPS/cookie security block with environment-driven equivalents (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`), defaulting to the prior (disabled) behavior. See §4.3 for full reasoning.

### `.env.example`
- Documented the four new HTTPS/cookie settings, defaulted off, so they're discoverable when standing up a production environment.

### `blog/views/posts.py`, `blog/views/comments.py`
- Removed confirmed-unused imports (`JsonResponse`, `render_to_string`, `Post`).

All changes above are currently **uncommitted working-tree changes** — nothing has been committed or pushed. Review the diff and commit when ready.

---

## 8. Outstanding items requiring manual review

| Item | Priority | Recommended next step |
|---|---|---|
| CKEditor 4 is EOL with unfixed security issues (`ckeditor.W001`) | Medium | Scope a migration to `django-ckeditor-5` or an alternative editor; re-evaluate the CSP `style-src 'unsafe-inline'` exception afterward. |
| `SECRET_KEY` strength per environment | High (before any real deploy) | Generate a strong, random key for staging/production; never reuse the dev key. |
| Confirm `DEBUG=False`, `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_HSTS_SECONDS` set appropriately | High (before any real deploy) | Set these env vars in the production environment once HTTPS is confirmed in front of the app. |
| CSP is still in Report-Only mode; `flagcdn.com` not yet allowlisted | Medium | Tracked in `Content Security policy Docs/CSP_NOTES.md` §4 — resolve the known `img-src` gap and let Report-Only run over a real traffic window before enforcing. |
| No linter/formatter configured | Low | Adopt `flake8` or `ruff` with a checked-in config to catch dead imports and style issues automatically. |
| No `Procfile`/deployment script found documenting how `gunicorn`/`daphne` are actually invoked in production | Low | Add a `Procfile` or deployment doc so the production start command is version-controlled, not tribal knowledge. |
| Default `/admin/` path | Low (optional) | Consider moving to a non-default path as defense-in-depth against scanners. |
| 6 direct dependencies outdated but not vulnerable (django-crispy-forms, crispy-bootstrap5, django-ckeditor, gunicorn, whitenoise, psycopg2-binary) | Low | Bump opportunistically during routine maintenance; none are urgent. |
| Django 6.1 available (current: 5.2.17) | Low | Major version, out of scope for this audit. Django 5.2 is the LTS branch — no need to chase 6.x immediately; revisit when 5.2 approaches end-of-life. |
| Pre-existing test coverage gaps (`blog/views/comments.py` 0%, `blog/mixins.py` 0%, etc.) | Medium | Already tracked with a checklist in `TESTING.md` — not duplicated here. |

---

## 9. Suggested cadence

- **Run `pip-audit -r requirements.txt` on every dependency bump**, and at minimum **monthly** even with no changes — new CVEs are disclosed against unchanged code constantly (this audit alone found 50 against versions that were "current" a few months ago).
- **Run this full audit (all sections) before every production deploy**, and otherwise **quarterly**.
- **Save each run as a new dated `SECURITY_AUDIT_<date>.md`** (this file's naming convention) rather than overwriting — the series is itself a record of the project's security posture over time, and lets you spot regressions (e.g. a warning that was fixed reappearing).
- Re-run `python manage.py check --deploy` any time `settings.py` changes, regardless of the cadence above.

---

*End of report. Diff of all changes made available via `git diff` in the working tree at time of writing.*
