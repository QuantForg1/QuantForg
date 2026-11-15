# Phase 6 — Institutional Intelligence delivery report

## Summary

Phase 6 productizes existing advisory analytics behind `/institutional-intelligence`
and seven Intelligence Center routes. No parallel trading stack. No LIVE enablement.

## Modules

1. `/intelligence-center` — hub
2. `/predictive-market-intelligence`
3. `/strategy-analytics`
4. `/predictive-risk`
5. `/portfolio-optimization`
6. `/execution-optimization`
7. `/decision-intelligence` (Phase 6 lifecycle + legacy workspace)
8. `/institutional-reports`

## Backend

- Domain: `app/domain/institutional_intelligence/`
- Service: `app/application/services/institutional_intelligence.py`
- Router: `/institutional-intelligence`
- Database: **no new migrations**

## Safety

- Never order_send / auto-rebalance / raise risk limits
- Forecasts include limitations; `guarantees_outcome=false`
- Approved recommendations never authorize LIVE

## Tests

- `tests/unit/test_phase6_institutional_intelligence.py`
- `frontend/src/lib/trading/phase6-intel-contract.test.ts`
