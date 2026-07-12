#!/bin/sh
# QuantForg container entrypoint — Railway / PaaS compatible.
set -eu

export APP_ENV="${APP_ENV:-${ENVIRONMENT:-production}}"
export ENVIRONMENT="${ENVIRONMENT:-$APP_ENV}"
export DEBUG=false
export RELOAD=false
export EXECUTION_ENABLED="${EXECUTION_ENABLED:-false}"
export ALLOWED_HOSTS="*"
export DOCS_ENABLED="${DOCS_ENABLED:-true}"

PORT="${PORT:-8000}"
export PORT
HOST="${HOST:-0.0.0.0}"
export HOST
# Force single worker — multi-worker has caused silent proxy failures on Railway.
WORKERS=1
export WORKERS

# Outage isolation: QF_MINIMAL=1 serves app.minimal_asgi:app (no middleware/lifespan).
# Default ON until Railway returns 200; set QF_MINIMAL=0 to restore full app.
QF_MINIMAL="${QF_MINIMAL:-1}"
export QF_MINIMAL

if [ "${QF_MINIMAL}" = "1" ]; then
  APP_TARGET="app.minimal_asgi:app"
else
  APP_TARGET="app.main:app"
fi

echo "quantforg_entrypoint python=$(python -c 'import sys; print(sys.version.split()[0])') APP_ENV=${APP_ENV} PORT=${PORT} HOST=${HOST} WORKERS=${WORKERS} QF_MINIMAL=${QF_MINIMAL} APP_TARGET=${APP_TARGET}"

# h11 + asyncio: most compatible with Railway's reverse proxy (avoid httptools/uvloop quirks).
# lifespan=off for minimal; on for full app.
if [ "${QF_MINIMAL}" = "1" ]; then
  exec python -m uvicorn "${APP_TARGET}" \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers 1 \
    --http h11 \
    --loop asyncio \
    --lifespan off \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --log-level info \
    --access-log
else
  exec python -m uvicorn "${APP_TARGET}" \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers 1 \
    --http h11 \
    --loop asyncio \
    --lifespan on \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --log-level info \
    --access-log
fi
