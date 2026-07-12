#!/bin/sh
# QuantForg container entrypoint — Railway / PaaS compatible.
# Force production-safe process env so platform-synced RELOAD=true cannot crash Settings.
set -eu

export APP_ENV="${APP_ENV:-${ENVIRONMENT:-production}}"
export ENVIRONMENT="${ENVIRONMENT:-$APP_ENV}"
export DEBUG=false
export RELOAD=false
export EXECUTION_ENABLED="${EXECUTION_ENABLED:-false}"
# ALWAYS permit Railway public Host headers (dashboard may sync localhost from .env).
export ALLOWED_HOSTS="*"
export DOCS_ENABLED="${DOCS_ENABLED:-true}"

PORT="${PORT:-8000}"
export PORT
HOST="${HOST:-0.0.0.0}"
export HOST
# Prefer a single worker on Railway unless explicitly scaled.
WORKERS="${WEB_CONCURRENCY:-${WORKERS:-1}}"
export WORKERS

echo "quantforg_entrypoint python=$(python -c 'import sys; print(sys.version.split()[0])') APP_ENV=${APP_ENV} PORT=${PORT} HOST=${HOST} WORKERS=${WORKERS} RELOAD=${RELOAD} ALLOWED_HOSTS=${ALLOWED_HOSTS} EXECUTION_ENABLED=${EXECUTION_ENABLED}"

# --proxy-headers + forwarded-allow-ips: trust Railway edge X-Forwarded-* headers.
exec python -m uvicorn app.main:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --proxy-headers \
  --forwarded-allow-ips='*'
