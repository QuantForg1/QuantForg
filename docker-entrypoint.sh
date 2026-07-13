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

# Railway injects PORT at runtime (commonly 8080). Never default to 8000 here —
# that mismatch leaves Networking → Public Domain → Port 8000 while Uvicorn
# listens on ${PORT}.
if [ -z "${PORT:-}" ]; then
  echo "FATAL: PORT is not set. Railway must inject PORT; do not bake PORT=8000 in the image." >&2
  exit 1
fi
export PORT

HOST="${HOST:-0.0.0.0}"
export HOST
WORKERS=1
export WORKERS

APP_TARGET="app.main:app"
LIFESPAN_FLAG="on"

echo "quantforg_entrypoint PORT=${PORT} HOST=${HOST} APP_TARGET=${APP_TARGET}"

python - <<'PY'
import os
import socket

port = int(os.environ["PORT"])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", port))
print(f"bind_probe_ok port={port}")
s.close()
PY

python -m uvicorn "${APP_TARGET}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers 1 \
  --http h11 \
  --loop asyncio \
  --lifespan "${LIFESPAN_FLAG}" \
  --proxy-headers \
  --forwarded-allow-ips='*' \
  --log-level info \
  --access-log &
UV_PID=$!

python scripts/railway_self_check.py || true

echo "uvicorn_pid=${UV_PID} listening=${HOST}:${PORT}"
wait "${UV_PID}"
