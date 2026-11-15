# Phase 7 — Autonomous Trading Control delivery report

## Summary

Phase 7 productizes a decision→validation→sizing→authorization→approval
workflow behind `/autonomous-trading-control` and four Autonomy routes.
Default OBSERVE_ONLY. No parallel OMS. No LIVE enablement from this phase.

## Modules

1. `/autonomous-trading` — decision workspace
2. `/autonomy-control` — mode control (default OBSERVE_ONLY)
3. `/decision-approvals` — bound-parameter approvals
4. `/trade-intelligence` — post-trade + feedback

## Backend

- Domain: `app/domain/autonomous_trading_control/`
- Service: `app/application/services/autonomous_trading_control.py`
- Router: `/autonomous-trading-control`
- Database: **no new migrations**

## Safety

- `phase7_live_dispatch=false`
- Never order_send / force trade_allowed / raise risk limits
- AUTHORIZED ≠ LIVE submit; Approved ≠ LIVE

## Tests

- `tests/unit/test_phase7_autonomous_trading_control.py`
- `frontend/src/lib/trading/phase7-autonomy-contract.test.ts`
