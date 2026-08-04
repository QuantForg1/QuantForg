#!/usr/bin/env bash
# Post-deploy trading-core runtime validation (manual / CI hook).
# Does not place orders. Expects railway CLI + authenticated context.
set -euo pipefail

SERVICE="${RAILWAY_SERVICE:-QuantForg}"
echo "=== Trading core runtime validation (service=$SERVICE) ==="

need() {
  local pattern="$1"
  local label="$2"
  if railway logs --service "$SERVICE" --filter "$pattern" 2>/dev/null | head -n 5 | grep -q .; then
    echo "PASS  $label"
  else
    echo "WARN  $label (pattern not seen in recent logs — confirm manually)"
  fi
}

need "Scheduler Tick" "Scheduler Running"
need "Scanning Symbols" "Continuous scan"
need "AI Decision" "AI Decision Engine"
need "ORDER ACCEPTED\|order_send" "OMS / Gateway path"
need "PME Active\|BREAK_EVEN\|TRAILING\|Position Closed" "PME Healthy"
need "FORCE_FIRST_TRADE = FALSE\|FORCE_FIRST_TRADE ignored" "Test overrides OFF"
need "gateway\|Gateway\|health" "Gateway activity"

echo "=== Manual confirms ==="
echo "- Gateway Connected"
echo "- MT5 Connected / login live"
echo "- Auto Trading enabled on control plane"
echo "- No FORCE_FIRST_TRADE / ALLOW_RISK_LOCK_OVERRIDE armed"
echo "Done."
