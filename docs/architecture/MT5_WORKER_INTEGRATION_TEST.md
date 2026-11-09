# MT5 Worker Integration Test (real Windows — not CI)

CI uses `MockMt5WorkerAgent`. That **does not** prove a real MetaTrader
session. Run this checklist on owner-approved Windows hosts with **demo**
accounts only. No real-money orders.

## Preconditions

- [ ] Phase 1B code deployed to a non-production API (or local)
- [ ] `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`
- [ ] Windows host with MT5 installed; agent started with `WORKER_SERVICE_TOKEN`
- [ ] Host registered in capacity ledger with free slots ≥ 3
- [ ] Three distinct demo MT5 logins (User A/B/C) — never share passwords in tickets

## Procedure

1. Provision worker for User A → Account A; connect with login/password/server.  
2. Repeat for User B and User C on the **same or separate** hosts.  
3. Confirm each agent reports lifecycle `ready` only after verify.  
4. Confirm UI/API `connected=true` only when lifecycle is `ready`.  
5. Kill Worker A process; confirm B and C heartbeats continue.  
6. Disconnect A; confirm B and C remain ready.  
7. Attempt second account for User A → must be rejected.  
8. Attempt User D to claim User A’s login → must be rejected.  
9. Attempt investor password → must fail with readonly rejection.  
10. Record CPU/RAM per host and concurrent ready count.

## Pass criteria

| Metric | Required |
| --- | --- |
| Concurrent READY demo sessions | ≥ 3 |
| Cross-tenant credential access | 0 |
| Collateral disconnects | 0 |
| Investor login accepted for trade worker | 0 |

Record results in a dated file under `docs/production/reports/` — do not
claim Production LIVE multi-user readiness from this demo alone.
