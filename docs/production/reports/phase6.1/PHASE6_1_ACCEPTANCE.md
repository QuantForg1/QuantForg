# Phase 6.1 — Durable dispatch queue acceptance

**Baseline merge before this work:** `9cce75c9`  
**Gates:** `MULTI_ACCOUNT_DISPATCH_ENABLED=false`, `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`

## Acceptance matrix

| Criterion | Result | Label |
|---|---|---|
| Durable enqueue + idempotency | PASS | Automated test verified |
| Concurrent claim single winner | PASS | Automated test verified |
| Restart recovery | PASS | Automated test verified |
| Stale lease expiry | PASS | Automated test verified |
| Ownership / foreign claim denied | PASS | Automated test verified |
| Kill switch isolates one user | PASS | Automated test verified |
| Revoked account cancels jobs | PASS | Automated test verified |
| Risk ceiling blocks delivery | PASS | Automated test verified |
| No secrets in public payload | PASS | Automated test verified |
| No `order_send` in queue module | PASS | Automated test verified |
| Real MT5 demo authentication | — | **BLOCKED** (no demo credentials) |
| Demo order execution | — | **BLOCKED** / Not authorized |
| Production migration applied | — | Report after deploy/Owner apply |

## External dependencies (separate authorization)

- Windows VPS / host capacity
- Demo broker credentials
- Staging disposable identities
- Owner approval to flip dispatch flag on staging
