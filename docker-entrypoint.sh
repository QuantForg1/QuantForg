#!/bin/sh
# QuantForg container entrypoint — Railway / PaaS compatible.
set -eu

export APP_ENV="${APP_ENV:-${ENVIRONMENT:-production}}"
export ENVIRONMENT="${ENVIRONMENT:-$APP_ENV}"
export DEBUG=false
export RELOAD=false
# Live trading defaults off. Operators may set EXECUTION_ENABLED=true in Railway
# only when MT5_GATEWAY_BASE_URL is configured (gateway order_send path).
export EXECUTION_ENABLED="${EXECUTION_ENABLED:-false}"
# OpenAPI docs off by default in production images (set DOCS_ENABLED=true to opt in).
export DOCS_ENABLED="${DOCS_ENABLED:-false}"

# Production-safe Host allowlist — never force bare '*' when we can be explicit.
# Operators may override via ALLOWED_HOSTS. Railway probes use .up.railway.app /
# healthcheck.railway.app; public traffic uses RAILWAY_PUBLIC_DOMAIN.
_default_hosts=".up.railway.app,healthcheck.railway.app,localhost,127.0.0.1"
if [ -n "${RAILWAY_PUBLIC_DOMAIN:-}" ]; then
  _default_hosts="${RAILWAY_PUBLIC_DOMAIN},${_default_hosts}"
fi
case "${ALLOWED_HOSTS:-}" in
  ""|"*")
    export ALLOWED_HOSTS="${_default_hosts}"
    ;;
  *)
    export ALLOWED_HOSTS
    ;;
esac

# CORS: prefer explicit CORS_ALLOWED_ORIGINS / CORS_ORIGINS from the platform.
# Seed https://$RAILWAY_PUBLIC_DOMAIN when unset so same-origin API UIs work.
if [ -z "${CORS_ALLOWED_ORIGINS:-}${CORS_ORIGINS:-}" ] && [ -n "${RAILWAY_PUBLIC_DOMAIN:-}" ]; then
  export CORS_ALLOWED_ORIGINS="https://${RAILWAY_PUBLIC_DOMAIN}"
fi

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

echo "quantforg_entrypoint PORT=${PORT} HOST=${HOST} APP_TARGET=${APP_TARGET} ALLOWED_HOSTS=${ALLOWED_HOSTS}"
echo "Server starting..."
echo "Environment loaded..."

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

# Non-blocking self-check after listen; uvicorn must remain foreground for SIGTERM.
(
  sleep 2
  python scripts/railway_self_check.py || true
) &

# exec so signals reach uvicorn (tini is PID 1 via Dockerfile ENTRYPOINT).
exec python -m uvicorn "${APP_TARGET}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers 1 \
  --http h11 \
  --loop asyncio \
  --lifespan "${LIFESPAN_FLAG}" \
  --proxy-headers \
  --forwarded-allow-ips='*' \
  --log-level info \
  --access-log
