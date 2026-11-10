# Phase 8 — ITE → durable dispatch integration contract

**Status:** Contract only. **Not implemented** in `institutional_ite_runtime`.  
**Gate:** Staging demo worker registration + claim/ACK proven; Owner keeps LIVE submit flags false.

## Prerequisites (all required)

1. Staging lab enqueue / claim / ACK / fail / recover proven against disposable workers
2. Spoofed assignment claim rejected
3. `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false` and `QUANTFORG_M1_MICRO_LIVE_SUBMIT=false`
4. `QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false`
5. Demo (or ownership-verified) broker identity available — no invented credentials
6. Postgres mirror + RLS verified for the target environment
7. Explicit Owner approval to set `MULTI_ACCOUNT_DISPATCH_ENABLED=true` on staging only

## Proposed call site

After ITE produces a qualified central signal (existing confluence / decision path), and **before** any OMS / gateway submit:

```text
CentralSignalIntent.create(...)
  → revalidate eligibility (ownership + readiness + risk)
  → DurableDispatchQueue.plan_and_enqueue(...)
  → workers claim/ACK via mt5-workers dispatch APIs
```

Hard rules at the call site:

- Re-run eligibility immediately before enqueue (stale readiness must block)
- Verify account ownership (`assert_own_user` / AccountReadiness.ownership_verified)
- Refuse enqueue when live-submit gate is on (fail closed; do not fan out)
- Idempotency key = signal idempotency key (no duplicate delivery)
- Never import or call order_send / gateway_client from the queue path
- Demo-only until a separate LIVE authorization phase

## Non-goals (Phase 8)

- No change to Weltrade LIVE Robot / OMS / PME / kill switches
- No automatic enablement of multi-account LIVE submit
- No VPS provisioning
- No silent fallback that skips eligibility

## Owner action to unblock implementation

1. Supply disposable staging demo MT5 credentials into protected `local.env` (`QF_DEMO_*`)
2. Confirm staging Railway redeploy includes lab-enqueue route
3. Approve staging-only `MULTI_ACCOUNT_DISPATCH_ENABLED=true` after demo proof report
4. Separate written approval naming `institutional_ite_runtime` before any ITE wiring PR
