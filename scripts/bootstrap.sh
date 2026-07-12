#!/usr/bin/env bash
# Bootstrap a local QuantForg development environment.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "==> Checking Python 3.13..."
if ! command -v python3.13 >/dev/null 2>&1; then
  echo "ERROR: python3.13 is required but not found on PATH."
  exit 1
fi

echo "==> Checking Poetry..."
if ! command -v poetry >/dev/null 2>&1; then
  echo "ERROR: Poetry is required. Install from https://python-poetry.org/"
  exit 1
fi

echo "==> Copying .env.example → .env (if missing)..."
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "    Created .env — review and update secrets before running in production."
fi

echo "==> Installing Poetry dependencies..."
poetry install

echo "==> Installing pre-commit hooks..."
poetry run pre-commit install

echo "==> Starting Docker infrastructure (Postgres + Redis)..."
if command -v docker >/dev/null 2>&1; then
  docker compose up -d postgres redis
else
  echo "WARNING: Docker not found. Start Postgres and Redis manually."
fi

echo ""
echo "Bootstrap complete."
echo "  Run the API:    make run"
echo "  Run tests:      make test"
echo "  Quality gate:   make check"
echo "  Full stack:     make docker-up"
