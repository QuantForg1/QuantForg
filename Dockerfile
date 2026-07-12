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
    ALLOWED_HOSTS=* \
    DOCS_ENABLED=true \
    WORKERS=1 \
    HOST=:: \
    PORT=8000 \
    QF_MINIMAL=1

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
# Root entrypoint (not blocked by scripts/* dockerignore rules).
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN chmod +x ./docker-entrypoint.sh \
    && chown -R quantforg:quantforg ${APP_HOME}

USER quantforg

EXPOSE 8000

# Liveness only — process must respond even when optional deps are down.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f "http://127.0.0.1:${PORT:-8000}/health/live" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/docker-entrypoint.sh"]
