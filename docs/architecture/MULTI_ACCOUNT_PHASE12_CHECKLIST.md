# Phase 12 — Production multi-account operational readiness (checklist)

**Status:** NOT COMPLETE — baseline + isolation audited; Production workers not ready; LIVE fan-out fail-closed.  
**Evidence:** `docs/production/reports/phase12/PHASE12_ACCEPTANCE_2026-11-14.md`  
**Depends on:** Phase 11 COMPLETE

## Hard locks

```text
FORCE_FIRST_TRADE=false
QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false
QUANTFORG_M1_MICRO_LIVE_SUBMIT=false
```

Preserve Production DISPATCH=true / LIVE_SUBMIT=true and Staging DISPATCH=true / LIVE_SUBMIT=false unless Owner review says otherwise.  
No unauthorized order_send. Preserve Weltrade LIVE singleton, OMS, Policy v16, P7 10%, SaaS/billing.

## Owner decisions blocking COMPLETE

1. Keep multi-account `live_submit_armed_refused` fail-closed **or** authorize OMS fan-out design phase.  
2. Authorize Production multi-account worker heartbeat/readiness program (or explicitly defer).  
3. Accept or reconcile `execution_workers` vs control-plane dual registry.
