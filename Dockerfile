# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Builder stage: compiles/downloads Python dependencies into a venv.
# Build tools live only here and are discarded from the final image.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# apt-get upgrade pulls in any Debian security patch released since this
# base image tag was last rebuilt upstream (see the final stage below for
# why that gap matters). build-essential covers the (unlikely, but not
# guaranteed) case where a pinned dependency has no prebuilt wheel for
# this platform/Python combo - psycopg2-binary, Pillow, nh3 etc. normally
# install from wheels alone.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy only the dependency manifest first so this layer is cached across
# rebuilds that don't touch requirements.txt.
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Final stage: slim runtime image, no compilers, non-root user.
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings

# This FROM starts a fresh copy of the base image - none of the builder
# stage's package upgrades carry over across a multi-stage build boundary,
# and this is the layer that actually ships and gets Trivy-scanned. Same
# reasoning as the builder stage: patches an OS-level CVE fix that already
# exists in Debian's repos but isn't baked into this image tag yet,
# without waiting on an upstream python:3.12-slim rebuild. See
# docs/security.md §7 for the Trivy fixable-CRITICAL/HIGH gate this keeps
# green.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Application source. .dockerignore keeps the real .env, local media/,
# collected staticfiles/, venv/, .git/, and other dev-only artifacts out
# of the build context entirely.
COPY . .

# Runtime-writable directories: collectstatic output and media uploads
# (both are normally replaced by volume mounts at `docker run`/compose
# time — see docker-compose.prod.yml — this just guarantees they exist
# and are owned by the non-root user before that mount happens).
RUN mkdir -p /app/staticfiles /app/media /app/logs \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
