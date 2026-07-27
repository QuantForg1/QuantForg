# Institutional AI Scalping Engine v6.2 — Directional Execution Fix

Keeps v6.1 hardening. Fixes BUY-preferring live OMS side selection.

## Root cause

1. `InstitutionalDecisionPipeline` sized risk from AI direction but
   `TradeDecisionEngine` used **ConfluenceEngine MTF** for `DecisionAction`.
   AI SELL + bullish confluence → **BUY OMS order**.
2. Force First Trade AUTO hard-defaulted flat bias → **BUY**.

## Fix

- `resolve_executable_direction()` — validated AI BUY/SELL is authoritative in
  scalping; opposite confluence → NO_TRADE; never invent BUY.
- Force First Trade: no direction → leave decision unchanged (no BUY default).
- Bridge `_build_intent`: explicit BUY→buy / SELL→sell only.

## Tests

`tests/unit/test_directional_execution_v62.py`
