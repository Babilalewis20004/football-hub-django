# Football Hub

[![Security Pipeline](https://github.com/Babilalewis20004/football-hub-django/actions/workflows/security.yml/badge.svg)](https://github.com/Babilalewis20004/football-hub-django/actions/workflows/security.yml)

Football Hub is a Django 5.2 editorial platform for publishing and
discussing football content: articles with an editorial workflow (draft →
review → approval → publish), categories and tagging, comments, user
roles, and a live chat/support-inbox feature built on Django Channels. It
is a server-rendered monolith (Django templates + Bootstrap 5 + a little
HTMX) backed by PostgreSQL, with Redis powering real-time messaging.

## Features

- **Editorial workflow** — role-based publishing pipeline (Admin / Editor
  / Author / Contributor / Reader) with draft, review, approval, and
  publish states. Every new account starts as a Reader; an Admin promotes
  users to Contributor/Editor from Django admin (see
  [docs/architecture/security-architecture.md](docs/architecture/security-architecture.md#authorization)).
- **Live chat & support inbox** — real-time messaging over WebSockets
  (Django Channels + Daphne), backed by Redis in multi-worker deployments.
- **Account security** — TOTP two-factor authentication (`django-otp`),
  progressive CAPTCHA and lockout after repeated failed logins, session
  inactivity timeouts.
- **Hardened by default** — a documented Content-Security-Policy, CSRF/
  session cookie hardening, and an automated CI security pipeline (SAST,
  dependency/secret/container scanning) on every push — see
  [docs/security.md](docs/security.md).
- **Optional Telegram announcements** — automatically posts to a Telegram
  channel when a post is published — see [TELEGRAM.md](TELEGRAM.md).

## Tech stack

Django 5.2 · PostgreSQL · Django Channels / Daphne (WebSockets) · Redis ·
Bootstrap 5 + HTMX · Docker Compose · pytest

See [docs/architecture/technology-stack.md](docs/architecture/technology-stack.md)
for the full, verified dependency list.

## Getting started

Docker Compose is the recommended way to run this project locally — it
starts the app, PostgreSQL, and Redis with no manual setup required.

```bash
git clone https://github.com/Babilalewis20004/football-hub-django.git
cd football-hub-django
cp .env.example .env   # Windows PowerShell: Copy-Item .env.example .env
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

Then open <http://localhost:8000>.

See the [Deployment Guide](docs/deployment.md) for complete local setup
and deployment instructions, including environment configuration,
troubleshooting, and the production Docker Compose configuration.

## Documentation

- [docs/deployment.md](docs/deployment.md) — full local setup and
  deployment guide
- [docs/docker.md](docs/docker.md) — day-to-day Docker Compose commands
- [docs/README.md](docs/README.md) — architecture, database schema, and
  UI documentation index
- [docs/security.md](docs/security.md) — CI/CD security pipeline
  (SAST, dependency/secret/container scanning)
- [TESTING.md](TESTING.md) — running the test suite

## Testing

```bash
python -m pytest -v
```

See [TESTING.md](TESTING.md) for coverage details, or
[docs/deployment.md#16-running-tests](docs/deployment.md#16-running-tests)
for running tests inside Docker.
