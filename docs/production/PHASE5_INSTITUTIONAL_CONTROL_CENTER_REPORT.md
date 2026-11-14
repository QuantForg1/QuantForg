# Phase 5 — Institutional Control Center delivery report

## Summary

Phase 5 productizes existing ops/governance/execution surfaces behind seven
canonical Control Center routes and a thin `/institutional-ops` aggregator.
No parallel trading architecture. No LIVE order submission from this phase.

## Modules

1. `/operations` — hub + robot start/pause/stop (existing APIs) + module links
2. `/strategy-lifecycle` — ISLM/IRDP mapped to 10 Phase 5 stages; LIVE gates
3. `/execution-intelligence` — persisted attempt metrics; `/execution-intel` redirect
4. `/account-orchestration` — multi-account / worker observe-only facade
5. `/risk-automation` — enforcement readout; trader prefs remain `/risk-center`
6. `/incident-center` — normalized PRP/ITE/worker incidents; safe recovery rules
7. `/governance` — unified pending approvals + redacted audit trail

## Backend

- Domain: `app/domain/institutional_ops_control/`
- Service: `app/application/services/institutional_ops_control.py`
- Router: `app/presentation/routers/institutional_ops_control.py` (`/institutional-ops`)
- Registered in `app/main.py`
- Database: **no new migrations**

## Frontend

- Desks under `frontend/src/components/ops/phase5/`
- Pages under `frontend/src/app/(app)/{operations,strategy-lifecycle,...}/`
- `institutionalOpsApi` in `endpoints.ts`
- `OPS_HREF_PREFIXES` + command-palette entries in `nav-config.ts`

## Safety confirmation

- No real LIVE orders submitted during implementation or tests
- No `order_send` / `FORCE_FIRST_TRADE` / kill-switch bypass
- Resume = start after pause (documented)
- Backtest pass ≠ LIVE (`live_deploy_allowed` requires explicit gates)

## Tests

- `tests/unit/test_phase5_institutional_ops_control.py`
- `frontend/src/lib/trading/phase5-ops-contract.test.ts`
