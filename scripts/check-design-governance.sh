#!/usr/bin/env bash
# Ensures Design Bible / governance docs remain present (ADR-0022).
# Docs-only check — does not execute application code.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REQUIRED=(
  "docs/design/README.md"
  "docs/design/product-governance.md"
  "docs/design/feature-lifecycle.md"
  "docs/design/ux-principles.md"
  "docs/design/design-tokens.md"
  "docs/design/typography.md"
  "docs/design/accessibility.md"
  "docs/design/performance-budgets.md"
  "docs/design/component-acceptance-checklist.md"
  "docs/design/feature-acceptance-checklist.md"
  "docs/adr/0022-design-bible-and-product-governance.md"
)

missing=0
for rel in "${REQUIRED[@]}"; do
  if [[ ! -f "$ROOT/$rel" ]]; then
    echo "MISSING: $rel"
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo "Design governance docs missing. See docs/design/README.md (ADR-0022)."
  exit 1
fi

echo "Design governance docs OK (${#REQUIRED[@]} files)."
