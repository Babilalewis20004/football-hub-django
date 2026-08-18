#!/bin/sh
# Container startup sequence for the Django/Daphne image.
#
# Runs on every container start (dev and prod alike): wait for Postgres,
# apply migrations, optionally collect static files, then hand off to
# whatever command was given (daphne by default, `manage.py runserver`
# in the dev override, `pytest` for test runs, etc.).
set -e

echo "entrypoint: waiting for database..."
python <<'PYEOF'
import os
import sys
import time

import psycopg2

host = os.environ.get("DB_HOST")
port = os.environ.get("DB_PORT")
name = os.environ.get("DB_NAME")
user = os.environ.get("DB_USER")
password = os.environ.get("DB_PASSWORD")

for attempt in range(1, 31):
    try:
        conn = psycopg2.connect(
            dbname=name, user=user, password=password, host=host, port=port,
            connect_timeout=3,
        )
        conn.close()
        print("entrypoint: database is accepting connections.")
        break
    except psycopg2.OperationalError as exc:
        print(f"entrypoint: database not ready yet ({attempt}/30): {exc}".strip())
        time.sleep(2)
else:
    sys.exit("entrypoint: database never became ready, giving up.")
PYEOF

echo "entrypoint: applying database migrations..."
python manage.py migrate --noinput

echo "entrypoint: setting up default roles..."
python manage.py setup_roles

# Skipped in the dev override (DJANGO_COLLECTSTATIC=0): with DEBUG=True,
# django.contrib.staticfiles serves STATICFILES_DIRS directly, so a
# collectstatic pass just slows down container start for no benefit.
if [ "${DJANGO_COLLECTSTATIC:-1}" = "1" ]; then
    echo "entrypoint: collecting static files..."
    python manage.py collectstatic --noinput
fi

if [ "$#" -eq 0 ]; then
    # No command supplied (the normal production path): serve HTTP and
    # WebSocket traffic through Daphne. Honours $PORT for container
    # platforms that inject their own port (see docs/docker.md).
    echo "entrypoint: starting Daphne on port ${PORT:-8000}..."
    exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
fi

exec "$@"
