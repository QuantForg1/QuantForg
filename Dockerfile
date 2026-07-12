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
    DEBUG=false

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

RUN chown -R quantforg:quantforg ${APP_HOME}

USER quantforg

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENTRYPOINT ["tini", "--"]
# Use python -m uvicorn (not bare "uvicorn"): Poetry console scripts copied from the
# builder stage keep a shebang pointing at /build/.venv/bin/python, which does not
# exist in the runtime image — tini then fails with "No such file or directory".
CMD [
    "python", "-m", "uvicorn",
    "app.main:app",
    "--host", "0.0.0.0",
    "--port", "8000",
    "--workers", "4"
]
