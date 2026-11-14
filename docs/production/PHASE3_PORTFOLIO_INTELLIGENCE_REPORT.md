# Phase 3 — Institutional Trading Intelligence & Portfolio Management — delivery report

**Branch:** `feat/phase3-portfolio-intelligence`  
**Freeze citation:** `docs/production/PHASE3_PORTFOLIO_INTELLIGENCE_FREEZE.md`

## Architecture audit (reuse)

| Layer | Reused | New |
|---|---|---|
| Live book | `PortfolioSyncService` / `GET /portfolio` | Household aggregator (call-only) |
| Registry | `broker_accounts` + Broker svc | Status honesty per account |
| Risk | `resolve_effective_risk`, Risk Center prefs | `aggregate_open_risk` tighten + household risk-check |
| OMS | `broker_submit_block_reason` | Thin household new-entry hook |
| Analytics | Deal history pairing patterns | Performance + attribution assembler |
| UI | Book panels (RC4) | `HouseholdDesk` + Book rail restore |

## Implemented modules

1. Multi-account household portfolio API (`/portfolio/household*`)
2. Exposure + concentration rollups
3. Cross-broker risk allocation + emergency stops (new orders only)
4. Strategy performance + trade attribution + CSV export
5. Book OS restore (`/book` canonical; `/portfolio` → `/book`)
6. Risk Center household gate wiring

## Key files

- `app/domain/portfolio_household/*`
- `app/application/services/household_portfolio_service.py`
- `app/presentation/routers/household_portfolio.py`
- `app/domain/institutional_trading/operations/live_prefs_tighten.py`
- `app/application/services/institutional_execution_engine.py` (thin hook)
- `frontend/src/components/book/household-desk.tsx`, `shell.tsx`
- `frontend/next.config.ts`, `nav-config.ts`, `risk-center/page.tsx`
- Tests: `tests/unit/test_phase3_household_portfolio.py`, `phase3-household-contract.test.ts`

## Migrations

None (reuse existing tables; in-process emergency stop store + audit trail).

## Portfolio data sources

- Active MT5 gateway snapshot (live)
- Owned `broker_accounts` registry (tenant-isolated)
- Honest `data_status`: live / cached / stale / disconnected / unavailable / unverified
- Missing metrics = `null` (never coerced to zero)
- FX conversion only with verified rates (otherwise excluded from convertible totals)

## Broker-by-broker availability

Eight-broker catalogue accounts appear when registered for the user. Unfunded / unreachable brokers remain `unavailable`/`disconnected` with null equity — never fabricated.

## Risk acceptance

- Prefs tighten-only including `aggregate_open_risk_pct` → exposure caps
- Household risk-check evaluate API
- Emergency stops block **new orders only**; no auto-close
- Global kill-switch unchanged

## Test results (local)

- Phase 3 unit: **10 passed**
- `pytest -m trading_core`: **2186 passed**, 3 xfailed
- Frontend phase3 contract: **ok**

## Safety

- No LIVE `order_send` in tests
- No second VPS / multi-LIVE fan-out
- No fabricated balances / FX / `trade_allowed`

## Remaining blockers (external)

- Unfunded brokers may lack equity / `trade_allowed`
- No verified FX feed → cross-currency totals partial
- Worker-unreachable accounts stay unavailable until readable snapshots exist
