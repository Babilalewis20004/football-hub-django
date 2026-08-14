# Deployment Architecture

**Important scope note:** this project contains no Dockerfile, no `docker-compose.yml`, no CI/CD pipeline configuration (no `.github/workflows/`, no `.gitlab-ci.yml`), and no `Procfile` or deployment script. Everything below describes what the codebase's own configuration (`config/settings.py`, `config/asgi.py`, `config/wsgi.py`, `requirements.txt`, `.env.example`) implies about how it is *meant* to be deployed — not a documented, executed deployment pipeline. Where the codebase is silent, this is stated explicitly rather than invented.

## Implied production topology

```text
                         Internet
                            |
                            v
                  Reverse proxy / TLS termination
                  (not present in this repo — implied
                   by SECURE_SSL_REDIRECT etc. being
                   env-driven, "enable after HTTPS is
                   configured")
                            |
              +-------------+-------------+
              |                           |
           HTTP                      WebSocket (ws/wss)
              |                           |
              v                           v
   -----------------------------------------------------
   |            ASGI application (config/asgi.py)       |
   |  ProtocolTypeRouter:                                |
   |    http       -> Django ASGI app (all sync views)   |
   |    websocket  -> AllowedHostsOriginValidator(        |
   |                    AuthMiddlewareStack(               |
   |                      URLRouter(chat.routing)))        |
   |  Served by: Daphne (daphne==4.2.3, in INSTALLED_APPS) |
   -----------------------------------------------------
              |                           |
              v                           v
        WhiteNoise                  Channel layer
     (serves STATIC_ROOT           (InMemoryChannelLayer
      via middleware)               if REDIS_URL unset,
              |                      else channels_redis
              |                      against Redis)
              v                           |
   PostgreSQL (django.db.backends.postgresql)  <--- also read by
                                            chat consumers (ORM)
```

## What the codebase confirms about the production server

- **ASGI, not WSGI, is required** for the live-chat feature: `config/asgi.py` defines the `ProtocolTypeRouter` that handles both HTTP and WebSocket traffic. A pure-WSGI deployment (`config/wsgi.py` alone, e.g. Gunicorn with sync workers and no ASGI adapter) would serve normal pages fine but **cannot serve `/ws/chat/...` WebSocket connections at all** — the chat widget, support inbox, and support room would be non-functional.
- **Daphne** is the ASGI server present in the dependency set (`daphne==4.2.3`) and registered in `INSTALLED_APPS` (required there specifically so Channels integrates with `manage.py runserver` during development). No process manager config (systemd unit, Supervisor config, `Procfile`) exists in the repo specifying the actual production start command (e.g. `daphne config.asgi:application`) — this is flagged as a gap in `SECURITY_AUDIT_2026-08-10.md` §8 and remains true as of this documentation.
- **Gunicorn** (`gunicorn==23.0.0`) is also pinned in `requirements.txt`. Given Gunicorn is a WSGI server, its presence alongside Daphne is only reconcilable in an ASGI deployment if it's used as a **process manager wrapping Uvicorn/Daphne workers** (Gunicorn supports `-k uvicorn.workers.UvicornWorker`-style ASGI worker classes) — but no such worker class or Gunicorn config file exists in this repo, and `uvicorn` itself is not a dependency. **Not determinable from the codebase** which of these two servers (or what combination) is actually used to run the app in production; both are simply present as pinned dependencies with no invocation documented.
- **WhiteNoise** removes the need for a separate static file server for correctness — `whitenoise.middleware.WhiteNoiseMiddleware` serves everything under `STATIC_ROOT` directly from the Django/ASGI process after `collectstatic` has been run. A reverse proxy in front is still expected (implied by the HTTPS-related settings), but its job would be TLS termination and (optionally) proxying `/media/` — not static file serving.
- **Media files** (`MEDIA_ROOT = media/`) are only served by Django itself when `DEBUG=True` (`config/urls.py`'s conditional `static()` route). In production (`DEBUG=False`), nothing in the codebase serves `/media/...` — this must be handled by the reverse proxy or another mechanism not present in this repo. This is a real gap: `Post.featured_image` and `CustomUser.avatar` uploads would be inaccessible in a naive production deployment unless something outside this codebase serves that path.

## Database

- **PostgreSQL only.** `DATABASES.default.ENGINE = 'django.db.backends.postgresql'`, with `NAME`/`USER`/`PASSWORD`/`HOST`/`PORT` all required environment variables (`config.py: config("DB_NAME")` etc. have no defaults — the app will fail to start without them, by design). SQLite is never referenced in settings; `db.sqlite3` is gitignored purely as a defensive habit, not because it's ever created.
- Migrations must be run (`python manage.py migrate`) as part of deployment — no auto-migrate-on-boot logic exists in the codebase.
- `collectstatic` must be run (`python manage.py collectstatic`) to populate `STATIC_ROOT` for WhiteNoise to serve.

## Redis / channel layer

- **Optional, environment-driven.** `REDIS_URL` (empty by default per `.env.example`). If set, `CHANNEL_LAYERS` uses `channels_redis.core.RedisChannelLayer` pointed at that URL; if unset, `channels.layers.InMemoryChannelLayer` is used instead.
- **This distinction is operationally significant, not cosmetic**: `InMemoryChannelLayer` only routes messages between consumers running inside the *same process*. If production runs more than one ASGI worker process (which any real deployment handling concurrent load would), chat messages sent to one worker's `ChatConsumer` would never reach a `SupportInboxConsumer` connected to a different worker — the support inbox and unread-badge features would silently miss messages. The code comment in `config/settings.py` states this directly: "Set `REDIS_URL` in production (and run more than one worker) to fan messages out across processes via channels_redis." Redis is therefore a **hard requirement for any multi-process production deployment of the chat feature**, even though the code will run without it.
- Not determinable from the codebase what Redis version, persistence configuration, or hosting (self-managed vs. managed service) is expected — none of that is specified anywhere in the repo.

## Environment variables (from `.env.example` — the authoritative list of what this app expects)

| Variable | Required? | Default | Purpose |
|---|---|---|---|
| `SECRET_KEY` | Yes (no default) | — | Django cryptographic signing key |
| `DEBUG` | No | `False` | Debug mode toggle |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Yes (no defaults) | — | PostgreSQL connection |
| `ALLOWED_HOSTS` | No | `127.0.0.1,localhost` | Comma-separated host allowlist |
| `REDIS_URL` | No | `""` (empty → in-memory channel layer) | Channels channel layer backend |
| `SECURE_SSL_REDIRECT` | No | `False` | Force HTTPS redirect |
| `SESSION_COOKIE_SECURE` | No | `False` | HTTPS-only session cookie |
| `CSRF_COOKIE_SECURE` | No | `False` | HTTPS-only CSRF cookie |
| `SECURE_HSTS_SECONDS` | No | `0` | HSTS header duration |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID` | No | `""` (empty → integration disabled) | Telegram publish announcements |
| `EMAIL_BACKEND` | No | `django.core.mail.backends.console.EmailBackend` | Password-reset email delivery |
| `DEFAULT_FROM_EMAIL` | No | `noreply@footballhub.local` | From-address for outgoing email |
| `LOGIN_MAX_FAILED_ATTEMPTS` | No | `5` | Lockout threshold |
| `LOGIN_LOCKOUT_MINUTES` | No | `15` | Lockout duration |
| `LOGIN_CAPTCHA_AFTER_ATTEMPTS` | No | `2` | Progressive CAPTCHA threshold |
| `SESSION_INACTIVITY_TIMEOUT` | No | `300` (5 min) | Session auto-logout window |
| `CSP_VIOLATION_REPORT_PATH` | No | `/csp-report/` | CSP report-collection endpoint |

`SECRET_KEY` and the five `DB_*` variables have no defaults in code — the application will refuse to start without them, which is a deliberate secrets-handling choice (confirmed correct in `SECURITY_AUDIT_2026-08-10.md`).

## Development vs. Production — what actually changes

| Aspect | Development (as configured by defaults) | Production (requires explicit configuration) |
|---|---|---|
| `DEBUG` | Defaults `False`, but typically set `True` in local `.env` | Must be `False` |
| Database | PostgreSQL (same engine as prod — **no SQLite fallback exists**) | PostgreSQL |
| Channel layer | `InMemoryChannelLayer` (default, no `REDIS_URL`) | `RedisChannelLayer` (required if running >1 worker) |
| ASGI server | `manage.py runserver` (Daphne-integrated via `INSTALLED_APPS`) | Not documented in-repo — implied to be Daphne (and possibly Gunicorn as a process manager) run directly, per dependencies |
| HTTPS | Off (`SECURE_SSL_REDIRECT=False` etc., correct for local HTTP) | Must be turned on via env vars once a reverse proxy terminates TLS in front |
| Media serving | Django serves `/media/` directly (`DEBUG=True` conditional route) | **Not handled by this codebase** — needs a reverse proxy or other mechanism outside the repo |
| Static files | WhiteNoise serves from `STATIC_ROOT` after `collectstatic` | Same — WhiteNoise works identically in both, no separate CDN/static server required for correctness |
| Email | Console backend (prints to stdout) | Must set `EMAIL_BACKEND` to a real SMTP backend via env var |
| CAPTCHA storage | Local DB table (`captcha_captchastore`) | Same — no external CAPTCHA service is used in either environment |

## Health checks, build process, startup process

**Not determinable from the codebase.** No health-check endpoint, readiness/liveness probe, build script, or startup script (beyond the standard `manage.py migrate` / `collectstatic` / run-server sequence implied by any Django project) exists anywhere in this repository.

## Secrets management

`.env` is gitignored and confirmed never committed (per `SECURITY_AUDIT_2026-08-10.md`, which checked `git log --all --full-history -- .env`). `.env.example` documents every variable with blank/safe defaults, intended as the template for a real `.env`. No secrets manager, vault, or cloud-provider secret store integration exists in the codebase — secret delivery to the running process (however that happens in the actual production environment) is outside this repo's scope.
