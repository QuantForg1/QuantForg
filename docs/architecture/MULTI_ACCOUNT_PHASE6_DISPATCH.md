# Multi-account Phase 6 — Dispatch architecture (non-executing)

**Status:** Architecture + dry-run foundation. LIVE fan-out **DISABLED**.  
**Depends on:** Phase 1 contracts, Phase 5/5.1 eligibility.

## Objective

Prepare safe signal dispatch from the central QuantForg engine to independently eligible user accounts **without** enabling OMS / MT5 order submission.

## Pipeline (target)

1. Central signal generation (`CentralSignalIntent`)
2. Signal validation + deduplication (idempotency key)
3. Per-user account eligibility (`evaluate_account_eligibility`)
4. Per-account effective risk (`resolve_effective_risk`)
5. Durable dispatch queue (foundation: in-memory ledger; DB queue later)
6. Idempotent dispatch keys (`signal_key:acct:{broker_account_id}`)
7. Isolated worker delivery — **not wired**
8. Worker acknowledgement — **not wired**
9. Execution result tracking — **not wired**
10. Per-account audit — **not wired**

## State machine (aligned with `AccountExecutionState`)

Existing vocabulary (do not fork):

```text
received → eligibility_pending → eligible | blocked
eligible → queued → submitting → acknowledged → partial_fill | filled
any non-terminal → rejected | cancelled | dead_letter
```

Phase 6 dry-run foundation may mark `queued` only when the dispatch **flag** is on, and **always** sets `delivery_suppressed=true`. It never enters `submitting`.

Suggested operator-facing labels (docs only):

| Operator label | Maps to |
|---|---|
| PENDING | `received` / `eligibility_pending` |
| ELIGIBILITY_CHECK | evaluation in progress |
| BLOCKED | `blocked` |
| QUEUED | `queued` (delivery suppressed until LIVE auth) |
| DELIVERED / ACKNOWLEDGED / EXECUTION_REPORTED | future worker phases |
| FAILED / EXPIRED / CANCELLED | `rejected` / `cancelled` / `dead_letter` |

## Safeguards

- One active MT5 account per user (DB unique indexes)
- One active worker per account / per user
- No shared terminal sessions or plaintext credentials in plans
- Idempotency prevents duplicate intents for the same signal+account
- Stale / missing workers → `BLOCKED`
- Revoked accounts → `BLOCKED`
- Global Owner ceilings always win via `resolve_effective_risk`
- `MULTI_ACCOUNT_DISPATCH_ENABLED=false`
- `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false`
- Dry-run module forces `live_submit_allowed=False` regardless of env mistakes

## Module

- `app/application/services/multi_account_dispatch_dry_run.py`
  - `plan_signal_dispatch(...)`
  - `InMemoryDispatchLedger`
- Tests: `tests/unit/test_phase6_dispatch_dry_run.py`

## Before demo execution

- Isolated Windows workers with proven MT5 auth
- Durable DB-backed queue + ack protocol
- Staging Supabase / test identities
- Explicit Owner approval to enable dispatch flag (still without LIVE submit)

## Before LIVE authorization

- Separate Owner-signed enablement of `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED`
- OMS / risk / Weltrade singleton regression green
- Per-account kill switches and monitoring
- No Exness/HFM LIVE without authenticated demo evidence
