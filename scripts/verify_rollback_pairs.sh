#!/usr/bin/env bash
# Static rollback verification: every up migration has a matching down file.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIG="${ROOT}/supabase/migrations"
DOWN="${MIG}/down"
missing=0
while IFS= read -r f; do
  stem="$(basename "$f" .sql)"
  if [[ ! -f "${DOWN}/${stem}.down.sql" ]]; then
    echo "MISSING down for $f" >&2
    missing=1
  fi
done < <(ls -1 "${MIG}"/*.sql | sort)
if [[ "$missing" -ne 0 ]]; then
  exit 1
fi
count="$(ls -1 "${MIG}"/*.sql | wc -l | tr -d ' ')"
echo "OK: ${count} up migrations each have a reversible down"
