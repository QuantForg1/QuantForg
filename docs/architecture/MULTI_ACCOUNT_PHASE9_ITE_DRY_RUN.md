# Phase 9 — ITE multi-account dry-run integration

**Status:** Implemented (non-executing).  
**Approval:** Product-owner Phase 9 assignment naming `institutional_ite_runtime`.  
**Baseline:** PR #234 / `9a8bc33e`.

## Architecture

```text
InstitutionalIteRuntime (qualified BUY/SELL + PRE_APPROVED)
  → attach_ite_multi_account_dry_run(...)   # thin hook, never raises into OMS
      → CentralSignalIntent (idempotency: ite:{decision_id}:{symbol}:{side})
      → resolve targets (explicit / diagnostics / provider; never invent)
      → if LIVE submit armed → refuse fail-closed
      → DurableDispatchQueue.plan_and_enqueue  # flag OFF → non-claimable audit jobs
          → evaluate_account_eligibility (ownership + worker + global risk)
      → diagnostics['multi_account_dry_run'] audit event
  → existing singleton Weltrade OMS path unchanged
```

## Safety locks (must remain false)

| Flag | Value |
|---|---|
| `MULTI_ACCOUNT_DISPATCH_ENABLED` | `false` |
| `MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED` | `false` |
| `QF_ALLOW_WORKER_ON_LIVE_TERMINAL` | `false` |

No `order_send`. No OMS from the multi-account path. No credentials in payloads.

## Demo authentication

`connect-demo` / sealed claim remain **BLOCKED** until Owner supplies protected `QF_DEMO_*`.  
Unit fixtures are labeled mocks — not actual MT5 authentication.

## Customer readiness ladder

`GET /multi-account/dispatch/status` exposes `readiness.*` flags that stay **false** without evidence.
