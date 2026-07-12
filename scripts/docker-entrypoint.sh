#!/bin/sh
# Railway (and most PaaS) inject PORT; bind there so the edge proxy can reach us.
set -eu
PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-${WORKERS:-1}}"
exec python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers "${WORKERS}"
