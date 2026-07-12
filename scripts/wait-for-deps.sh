#!/usr/bin/env bash
# Wait for PostgreSQL and Redis to become healthy, then exit.
# Useful in CI and docker entrypoints.
set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
TIMEOUT="${WAIT_TIMEOUT:-60}"

echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT} (timeout ${TIMEOUT}s)..."
elapsed=0
until (echo >"/dev/tcp/${POSTGRES_HOST}/${POSTGRES_PORT}") >/dev/null 2>&1; do
  sleep 1
  elapsed=$((elapsed + 1))
  if [[ ${elapsed} -ge ${TIMEOUT} ]]; then
    echo "ERROR: PostgreSQL did not become ready within ${TIMEOUT}s"
    exit 1
  fi
done
echo "PostgreSQL is ready."

echo "Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT} (timeout ${TIMEOUT}s)..."
elapsed=0
until (echo >"/dev/tcp/${REDIS_HOST}/${REDIS_PORT}") >/dev/null 2>&1; do
  sleep 1
  elapsed=$((elapsed + 1))
  if [[ ${elapsed} -ge ${TIMEOUT} ]]; then
    echo "ERROR: Redis did not become ready within ${TIMEOUT}s"
    exit 1
  fi
done
echo "Redis is ready."
echo "All dependencies are reachable."
