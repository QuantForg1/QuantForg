# QuantForg Dockerfile
# Multi-stage build for a lean, production-ready Python 3.13 image.

# ---------------------------------------------------------------------------
# Stage 1: Builder — install dependencies with Poetry
# ---------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry

WORKDIR /build

COPY pyproject.toml poetry.lock* ./

RUN poetry install --only main --no-root \
    && rm -rf "${POETRY_CACHE_DIR}"

COPY app ./app
COPY core ./core
COPY alembic ./alembic
COPY alembic.ini ./

RUN poetry install --only main

# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal production image
# ---------------------------------------------------------------------------
FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    PATH="/app/.venv/bin:$PATH" \
    APP_ENV=production \
    ENVIRONMENT=production \
    DEBUG=false \
    RELOAD=false \
    EXECUTION_ENABLED=false \
    DOCS_ENABLED=false \
    WORKERS=1 \
    HOST=0.0.0.0
# ALLOWED_HOSTS / CORS_ALLOWED_ORIGINS are set at runtime by docker-entrypoint.sh
# from RAILWAY_PUBLIC_DOMAIN (never bake Host=* into the image).

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libpq5 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 quantforg \
    && useradd --uid 1000 --gid quantforg --shell /bin/bash --create-home quantforg

WORKDIR ${APP_HOME}

COPY --from=builder /build/.venv ./.venv
COPY --from=builder /build/app ./app
COPY --from=builder /build/core ./core
COPY --from=builder /build/alembic ./alembic
COPY --from=builder /build/alembic.ini ./alembic.ini
COPY docker-entrypoint.sh ./docker-entrypoint.sh
COPY scripts/railway_self_check.py ./scripts/railway_self_check.py

RUN chmod +x ./docker-entrypoint.sh \
    && chown -R quantforg:quantforg ${APP_HOME}

USER quantforg

# Do NOT set PORT in the image. Railway injects PORT at runtime (e.g. 8080).
# Baking PORT=8000 caused the public domain target port to be pinned to 8000
# while the process correctly listened on Railway's injected PORT.

# tini as PID 1 for correct SIGTERM / zombie reaping on Railway deploys.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/docker-entrypoint.sh"]
