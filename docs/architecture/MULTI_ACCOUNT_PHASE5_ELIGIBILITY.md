# Multi-account Phase 5 — Preference-aware eligibility (dry-run)

**Status:** Implemented (code + unit tests). LIVE fan-out remains **off**.  
**Depends on:** Phase 1a contracts (`signal_dispatch`, `effective_risk`, feature gates), Phase 4 `user_risk_settings`.

## Objective

Bridge Phase 4 persisted customer risk preferences into per-account signal eligibility so each account can be classified `eligible` / `blocked` with `resolve_effective_risk`, without enabling multi-account LIVE dispatch or submit.

## Module

- `app/application/services/multi_account_eligibility_service.py`
  - `evaluate_account_eligibility(...)`
  - Ownership enforced via `assert_own_user`
  - Uses `resolve_effective_risk` for ceilings
  - Reports `dispatch_allowed` / `live_submit_allowed` / `dry_run`
  - **Never** calls OMS / order_send / PME / gateway

## Gates (unchanged defaults)

```text
MULTI_ACCOUNT_DISPATCH_ENABLED=false
MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false
```

When dispatch is false, evaluations still return ELIGIBLE/BLOCKED for inspection (`dry_run=true`). Callers must not enqueue worker submit.

## Out of scope

- Enabling LIVE multi-account flags
- Exness/HFM LIVE
- Changes to Owner hard ceilings / ITE / OMS / Weltrade singleton path
- Windows VPS / paid infra

## Tests

- `tests/unit/test_phase5_multi_account_eligibility.py`
