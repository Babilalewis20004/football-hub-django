# Deployment Architecture

**Scope note:** as of this Dockerization, the project has a `Dockerfile`,
`docker-compose.yml` (+ `docker-compose.override.yml` for dev,
`docker-compose.prod.yml` for production), `docker/entrypoint.sh`, and
`docker/nginx/default.conf` — see [Current Docker
architecture](#current-docker-architecture) below and
[docs/docker.md](../docker.md) for day-to-day commands. As of
`.github/workflows/security.yml`, the project also has a CI/CD **security**
pipeline (SAST, dependency/secret/container scanning, and the existing test
suite) that runs on every push and PR — see
[docs/security.md](../security.md) for the full architecture. There is
still no *deployment* automation (no build/push/deploy job anywhere) —
deployment remains manual. The rest of this document (below the Docker
section) is the original pre-Docker analysis of what the codebase's own
configuration implies about deployment; it's kept because it's still
accurate background for *why* the Docker setup is shaped the way it is,
not because it's now the primary source of truth.

## Current Docker architecture

```text
                              Internet
                                 |
                                 v
                    +-------------------------+
                    |  Nginx (:80, published)  |
                    |  docker/nginx/default.conf |
                    +------------+-------------+
                       |                    |
              /media/* served          everything else
              directly from                 |
              media_data volume             v
                       |          +-------------------+
                       |          |  web (Daphne)     |
                       |          |  config.asgi:      |
                       |          |  application       |
                       |          |  (internal only,   |
                       |          |   no host port)    |
                       |          +----+-----------+---+
                       |               |           |
                       v               v           v
                 media_data       postgres:5432  redis:6379
                 (volume)         (internal only) (internal only)
                                       |
                                 postgres_data
                                 (volume)
```

Production (`docker-compose.yml` + `docker-compose.prod.yml`): four
containers — `nginx`, `web`, `postgres`, `redis` — on one internal Docker
network (`backend`). Development (`docker-compose.yml` +
`docker-compose.override.yml`, the default for plain `docker compose up`):
three containers, no `nginx` — `web` runs `manage.py runserver` directly
on a published `:8000`, with the project directory bind-mounted for live
editing, since a single-host dev loop doesn't need the media-serving proxy
that production requires.

**Why Nginx, specifically:** not for TLS termination (none is configured —
see docs/docker.md's "Limitations" section) and not for static files
(WhiteNoise already serves those correctly from inside the `web` process,
untouched by Docker). It exists to close a real, pre-existing gap
confirmed below: **nothing in this codebase serves `/media/...` when
`DEBUG=False`.** Nginx serves media directly from the shared `media_data`
volume and reverse-proxies everything else (including `/ws/...` WebSocket
upgrades) to Daphne. Without it, avatar and post-image uploads would
404 in any production run of this container image.

**ASGI server, resolved:** `daphne -b 0.0.0.0 -p 8000 config.asgi:application`
is the production startup command (`docker/entrypoint.sh`, after
`migrate`/`collectstatic`). This was previously "not determinable from the
codebase" (§ below); it's now pinned down by the Docker implementation,
answering the open question about Gunicorn vs. Daphne: **Gunicorn is not
invoked anywhere in this Docker setup.** It remains in `requirements.txt`
(not removed — no evidence it's used elsewhere, so removing it wasn't
warranted) but plays no runtime role in the Dockerized deployment; ASGI/
WebSocket support requires either Daphne directly or Gunicorn wrapping a
`uvicorn.workers.UvicornWorker`-style ASGI class, and neither `uvicorn`
nor a Gunicorn worker-class config exists in this repo.

**Redis, resolved:** included as a service in both dev and production
Compose files, reached via `REDIS_URL=redis://redis:6379/0` (the Compose
service name — set directly in `docker-compose.yml`, overriding whatever
`.env` has, since `.env`'s value needs to stay valid for running the app
natively too). This makes `CHANNEL_LAYERS` use
`channels_redis.core.RedisChannelLayer` in every Docker Compose run,
resolving the "hard requirement for any multi-process production
deployment" flagged below — verified working end-to-end (WebSocket message
sent from one connection, round-tripped through Redis, received back and
persisted to Postgres) as part of this Dockerization's testing.

**Media, resolved:** `MEDIA_ROOT`/`MEDIA_URL` are unchanged in
`config/settings.py` (they were already Docker-compatible — relative to
`BASE_DIR`, no code change needed). What changed is *what serves them* in
production: Nginx, from the `media_data` named volume (`docker-compose.prod.yml`),
mounted read-write into `web` and read-only into `nginx`. This is a
single-host Docker volume, not object storage — see docs/docker.md's
"Limitations" section for what that does and doesn't guarantee.

**What's unchanged:** no application code, models, migrations, URLs,
authentication/authorization logic, or security settings were modified to
make this work — see docs/docker.md and the final Docker implementation
report for the full list of what was (and deliberately wasn't) touched.

### Future infrastructure recommendations (not implemented)

These are explicitly **not** part of the current implementation — listed
so they aren't mistaken for gaps in this Dockerization, and to distinguish
"not needed for this scope" from "not done":

- **TLS termination** — either a managed load balancer in front of the
  Docker host, or extending `docker/nginx/default.conf` with real
  certificates. See docs/docker.md's `SECURE_PROXY_SSL_HEADER` note before
  doing this.
- **Object storage for media** (S3-compatible) — would remove the
  single-host limitation on uploads; explicitly out of scope per this
  task's constraints, not attempted.
- **CD (deployment automation)** — `.github/workflows/security.yml` covers
  CI security scanning (see [docs/security.md](../security.md)) but there is
  still no automated build/push/deploy job; deployment remains manual.
- **Multi-host orchestration** (Kubernetes, Swarm, ECS, etc.) — this setup
  is single-host Docker Compose by design; out of scope.
- **A real application health endpoint** — the current `web` healthcheck
  is a bare TCP connect (see docs/docker.md), not an app-level readiness
  check (e.g. verifying DB connectivity from inside the view). Adding one
  would be an application code change, not a Docker config change, and
  wasn't made here to avoid inventing an API the codebase doesn't already
  have.

## Implied production topology (pre-Docker analysis, kept for context)

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
| `LOGIN_LOCKOUT_MINUTES` | No | `2` | Lockout duration |
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
