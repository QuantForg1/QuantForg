#!/usr/bin/env bash
# Verify Supabase SQL migrations apply from an empty database and roll back.
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@localhost:5432/quantforg_verify \
#     ./scripts/verify_migrations.sh
#
# Requirements: psql, empty target database (or one you are willing to wipe).
# Does not enable EXECUTION_ENABLED. Does not modify application code.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIG="${ROOT}/supabase/migrations"
DOWN="${MIG}/down"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi

echo "==> Applying ups in order"
mapfile -t UPS < <(ls -1 "${MIG}"/*.sql | sort)
for f in "${UPS[@]}"; do
  echo "  apply $(basename "$f")"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "$f" >/dev/null
done

echo "==> Applying downs in reverse order"
mapfile -t DOWNS < <(ls -1 "${DOWN}"/*.down.sql | sort -r)
for f in "${DOWNS[@]}"; do
  echo "  down $(basename "$f")"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "$f" >/dev/null
done

echo "==> Re-applying ups (idempotency / second pass)"
for f in "${UPS[@]}"; do
  echo "  re-apply $(basename "$f")"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "$f" >/dev/null
done

echo "OK: migrations verified from empty DB + rollback + re-apply"
