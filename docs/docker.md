# Docker

Football Hub runs as three containers (`web`, `postgres`, `redis`) plus, in
production, a fourth (`nginx`). This document covers day-to-day commands.
For *why* the architecture looks like this, see
[architecture/deployment-architecture.md](architecture/deployment-architecture.md)
and [architecture/system-architecture.md](architecture/system-architecture.md).

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin on Linux)
- Docker Compose v2 (`docker compose`, not the standalone `docker-compose`)

## One-time setup

Copy the example env file and fill in real values (a strong `SECRET_KEY`, a
database password, etc.):

```bash
cp .env.example .env
```

`.env` is read two ways: Django itself reads it via `python-decouple`, and
Docker Compose reads it to fill in `${POSTGRES_DB}`-style placeholders and
to populate each container's environment (`env_file:`). It is never copied
into the image (see `.dockerignore`) — only injected at container-start
time, so rebuilding the image doesn't require rebuilding secrets into it.

`POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD` (used to initialize the
`postgres` container) must match `DB_NAME`/`DB_USER`/`DB_PASSWORD` (used by
Django to connect) — see the comments in `.env.example`.

## Development

```bash
docker compose up
```

This merges `docker-compose.yml` (services) with `docker-compose.override.yml`
(dev-only settings) automatically — no flags needed. What you get:

- The whole project directory bind-mounted into the container, so edits on
  the host are picked up immediately.
- `python manage.py runserver 0.0.0.0:8000`, Channels/WebSocket-capable
  because `daphne` is registered in `INSTALLED_APPS` (see
  `config/settings.py`) — this is the same dev server behavior the project
  already had outside Docker.
- `DEBUG=True` (from `.env`), so static files are served by
  `django.contrib.staticfiles` directly from `static/` — no `collectstatic`
  step, and media uploads land in `./media` on the host, same as running
  natively.
- App reachable at **http://localhost:8000**.
- Postgres and Redis are present but **not** published to the host — only
  reachable from other containers, at `postgres:5432` / `redis:6379`.

Run in the background:

```bash
docker compose up -d
```

View logs:

```bash
docker compose logs -f          # all services
docker compose logs -f web      # just the app
```

Stop:

```bash
docker compose down
```

**`docker compose down -v` deletes the named volumes** — this destroys the
Postgres database (`postgres_data`) permanently. In dev, media lives in the
bind-mounted `./media` on the host, so it survives `-v`; in production it
would also be destroyed, since production keeps media in a named volume
(`media_data`). Never run `-v` against a database you care about without a
backup.

## Production

Explicitly combine the base file with the production overrides:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

(`docker-compose.override.yml` is only auto-merged when no `-f` flags are
given, so this command does not pick it up.)

What's different from dev:

- No source bind mount — the image is immutable; a code change requires a
  rebuild.
- The container's own `ENTRYPOINT` (see `docker/entrypoint.sh`) runs
  `collectstatic` on every start, then execs `daphne -b 0.0.0.0 -p 8000
  config.asgi:application` — real ASGI server, not the dev server.
- `web` publishes no host port. **Nginx** is the only container reachable
  from outside, on `:80` — it reverse-proxies everything to `web:8000`
  (including `/ws/...` WebSocket upgrades) and serves `/media/...` directly
  from the `media_data` volume, because nothing in the Django codebase
  itself serves media once `DEBUG=False` (see deployment-architecture.md).
- Media persists in the `media_data` named volume, shared read/write by
  `web` and read-only by `nginx`.
- All services restart automatically (`restart: unless-stopped`) unless
  you stop them explicitly.

Set `DEBUG=False` and a strong, unique `SECRET_KEY` in `.env` before running
this. See "Before enabling HTTPS" below before setting
`SECURE_SSL_REDIRECT=True`.

## Database migrations

Migrations run automatically on every container start (`docker/entrypoint.sh`
runs `python manage.py migrate --noinput` before the server starts, in both
dev and production). To run them manually — e.g. after pulling new
migration files without restarting the container:

```bash
docker compose exec web python manage.py migrate
```

## Create a superuser

```bash
docker compose exec web python manage.py createsuperuser
```

## Run tests

The test runners (`pytest`, `pytest-django`, `pytest-cov`) are dev
dependencies (`requirements-dev.txt`), deliberately **not** installed in
the image — a production image shouldn't carry test tooling. To run the
suite against a container, install them into the running container first:

```bash
docker compose exec web pip install -r requirements-dev.txt
docker compose exec web python -m pytest -v
docker compose exec web python -m pytest --cov=blog --cov-report=term-missing
```

This installs into the container's writable layer, not the image — it
does not persist across `docker compose build` / container recreation, and
does not affect the production image at all.

## Rebuild

After changing `requirements.txt`, the `Dockerfile`, or (in production)
application code:

```bash
docker compose build web
docker compose up -d
```

Force a clean rebuild ignoring the layer cache:

```bash
docker compose build --no-cache web
```

## Remove volumes (destructive)

```bash
docker compose down -v
```

**Warning:** this deletes `postgres_data` (the entire database) and, in
production, `media_data` (every uploaded avatar/post image) permanently.
There is no confirmation prompt. Back up first if the data matters.

## Networking

Every inter-container hostname is a Compose service name, resolved via
Docker's internal DNS — never `localhost`:

```
web  --> postgres:5432   (DB_HOST=postgres, set in docker-compose.yml)
web  --> redis:6379      (REDIS_URL=redis://redis:6379/0, set in docker-compose.yml)
nginx --> web:8000        (production only)
```

Inside a container, `localhost` refers to *that container itself*, not the
host machine or any other container — `web` trying to reach Postgres at
`localhost:5432` would be connecting to itself (which isn't listening on
that port), not to the `postgres` container. This is why `DB_HOST` and
`REDIS_URL` are overridden at the Compose level rather than left at
whatever `.env` has (which stays `localhost`/blank, correct for running
the app natively outside Docker).

Only `web` (dev) and `nginx` (production) publish a port to the host.
Postgres and Redis never do, in either environment — nothing outside the
`backend` Docker network can reach them directly.

## Health checks

- **postgres**: `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB`
- **redis**: `redis-cli ping`
- **web**: no application health endpoint exists in this codebase (and one
  wasn't added just for this), so the healthcheck only confirms something
  is listening on the app port (a plain TCP connect via a one-line Python
  script). It cannot tell you the app is *correctly* serving requests, only
  that the process is up.

`web` waits for `postgres`/`redis` via `depends_on: condition:
service_healthy`, which only means those healthchecks are passing — it
does not guarantee Django's specific credentials/database are ready the
instant Postgres starts accepting TCP connections. `docker/entrypoint.sh`
adds a second line of defense: it polls the actual Django database
connection (via `psycopg2`, up to 30 attempts, 2s apart) before running
`migrate`, so a slow Postgres start can't race the app into crashing on
boot.

## Deployment platform compatibility

The image is portable to any container-hosting platform (Fly.io, Railway,
Render, ECS, Cloud Run, a bare VM with Docker, etc.), not tied to Compose:

- **Port**: `docker/entrypoint.sh` binds Daphne to `$PORT` if set, falling
  back to `8000`. Platforms that inject their own port (Cloud Run, Render,
  Railway) are handled automatically; platforms that don't (a plain VM) get
  `8000`.
- **Startup command**: the image's `ENTRYPOINT` already runs
  migrate → collectstatic → `daphne -b 0.0.0.0 -p $PORT config.asgi:application`
  with no arguments needed — deploy the image as-is.
- **Required environment variables**: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`,
  `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` (all required —
  no defaults, the app refuses to start without them). See `.env.example`
  for the full list including optional settings.
- **PostgreSQL**: any reachable Postgres instance works — managed (RDS,
  Cloud SQL, Neon, etc.) or self-hosted. Point `DB_HOST`/`DB_PORT` at it.
- **Redis**: required for the chat feature to work correctly the moment
  more than one app instance/worker is running (see
  deployment-architecture.md for why) — point `REDIS_URL` at any reachable
  Redis. Optional only for a strictly single-process deployment.
- **Persistent media**: the platform must provide a persistent volume
  mounted at `/app/media`, or media uploads vanish on every redeploy. If
  the platform has no persistent-volume concept, media storage needs
  rethinking (e.g. object storage) — out of scope for this Dockerization,
  see "Limitations" below.
- **WebSockets**: the platform's router/load balancer must support
  WebSocket upgrade passthrough (most container platforms do; verify
  before relying on it). No separate configuration is needed on the Django
  side — `config/asgi.py` already routes `websocket` scope traffic.

## Before enabling HTTPS (`SECURE_SSL_REDIRECT=True`)

If you terminate TLS in front of this stack (a managed load balancer, or
extending `docker/nginx/default.conf` with a `listen 443 ssl` block), set
`SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` in
`config/settings.py` and make sure whatever proxy sits in front sets
`X-Forwarded-Proto` correctly (the bundled `docker/nginx/default.conf`
already does). Without this, Django can't tell the original request was
HTTPS — it sees plain HTTP from Nginx — and turning on
`SECURE_SSL_REDIRECT` would redirect-loop every request. This setting was
**not** added automatically as part of this Dockerization (it's a
behavior change to `config/settings.py`, and `SECURE_SSL_REDIRECT` stays
off by default, so nothing breaks today) — add it deliberately when you
actually put TLS in front of the stack.

## Limitations (read before calling this "production ready")

- **Media storage is a single-host Docker volume, not object storage.** It
  persists across container restarts/redeploys on the *same* Docker host,
  but does not survive migrating to a different host, does not scale
  beyond one host, and has no built-in backup/replication. This is
  appropriate for a single-VM deployment; it is not equivalent to S3 or
  similar, and nothing here implements that.
- **No TLS is configured.** `docker/nginx/default.conf` serves plain HTTP
  on `:80`. A real deployment needs TLS termination — either put this
  stack behind a managed load balancer that terminates TLS, or extend the
  Nginx config with real certificates.
- **No CI/CD.** Deployment is manual (`docker compose build && up -d` on
  the target host, or pushing the image to whatever registry/platform you
  use). None was added, per the task scope.
