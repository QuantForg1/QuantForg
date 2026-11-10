# Multi-account Phase 7 — Operational observability

**Status:** Read-only ops surfaces. LIVE fan-out remains **DISABLED**.

## Objective

Provide safe multi-user dispatch and worker visibility without enabling OMS submission.

## Shipped

| Surface | Path | Auth |
|---|---|---|
| Owner/worker aggregate | `GET /mt5-workers/ops/summary` (+ `dispatch_queue` metrics) | Worker service token |
| Customer own status | `GET /multi-account/dispatch/status` | Authenticated user (own rows) |
| Ops service | `app/application/services/multi_account_ops_service.py` | — |

## Metrics exposed

- Queue depth and counts by delivery / execution state
- Claimed / failed / dead-letter / kill-switched counts
- Feature flag values (dispatch + LIVE submit)
- Explicit `live_submit_allowed: false`

## Explicitly out of scope

- Enabling `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED`
- Demo/LIVE order execution
- Sharing Weltrade singleton across users
- Purchasing Windows VPS capacity

## Remaining

- Apply lease migration on Production Supabase (Owner ops)
- Wire Postgres claim path with `FOR UPDATE SKIP LOCKED` under staging load
- Authenticated Windows demo evidence
- Customer UI card for dispatch status (Design Freeze — only if product-owner requests)
