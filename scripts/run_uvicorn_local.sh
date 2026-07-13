#!/usr/bin/env bash
# Local Railway-parity boot for import/health verification.
# Does not source .env (avoids weak local POSTGRES_PASSWORD failing production validation).
set -euo pipefail
cd "$(dirname "$0")/.."
export APP_ENV=production
export EXECUTION_ENABLED=false
export DURABLE_PERSISTENCE="${DURABLE_PERSISTENCE:-false}"
export HEALTH_CHECK_TIMEOUT_SECONDS="${HEALTH_CHECK_TIMEOUT_SECONDS:-1}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1,testserver}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:3000}"
export PORT=8080
export SECRET_KEY="${SECRET_KEY:-a-real-production-secret-key-with-enough-entropy-here-xx}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-local-prod-password-not-dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://quantforg:${POSTGRES_PASSWORD}@127.0.0.1:5432/quantforg}"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080
