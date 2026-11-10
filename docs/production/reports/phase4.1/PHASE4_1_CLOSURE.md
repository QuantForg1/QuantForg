# Phase 4.1 — Risk Center Production Acceptance Closure

**Status:** IMPLEMENTATION COMPLETE — FINAL ACCEPTANCE PARTIALLY BLOCKED  
**Closed (implementation):** 2026-11-10  
**Baseline SHA (Risk Center):** `d1c2bce3` (PR #224)  
**Frontend Production (at closure):** `e9df4614` / later `26a1438f` (Live Market follow-ups #225–#226)  
**Railway API (at closure probes):** `d1c2bce3` Online  

## What shipped (Phase 4 / 4.1)

- Customer Risk Center preferences via `/api/v1/risk/preferences*`
- Persistence table `public.user_risk_settings` (RLS enabled + forced)
- Owner Policy remains on `/api/v1/admin/control` (OWNER-only)
- Overview cleanup: Trading Performance retained; Risk/Robot/Notifications/Activity panels removed from Overview
- Dedicated destinations retained: Risk Center, `/notifications`, `/ai-robot`, Positions, History

## Live Production evidence (verified)

| Check | Result |
|---|---|
| Preference Save (P7) 20.0 → 10.0 | VERIFIED — API `persisted=true`, `source=user_edit` |
| Database row | VERIFIED — 1 active row, `planned_risk_pct=10.0000` |
| Refresh persistence | VERIFIED |
| Foreign-user surface | VERIFIED — prefs API always caller-scoped (no foreign `user_id`) |
| Out-of-range prefs | VERIFIED — HTTP 422 `risk_preference_rejected` |
| Mandatory stop-loss copy | VERIFIED — cannot be disabled via prefs API |
| Unauth prefs / admin | VERIFIED — HTTP 401 |
| Owner overview (Owner session) | VERIFIED — HTTP 200 |
| Multi-account LIVE flags | VERIFIED — submit/dispatch false |
| Weltrade LIVE | VERIFIED — unchanged; no orders submitted |

## Blocked production acceptance (credentials)

| Test | Status | Missing prerequisite |
|---|---|---|
| P7 logout → fresh login → preference still 10% | **BLOCKED** | Secure P7 password and/or `QUANTFORG_CUSTOMER_TOKEN` for re-auth. Do not Sign out without these. |
| Ordinary non-owner Owner Policy denial (403) | **BLOCKED** | Separate ordinary (non-owner) customer session / `QUANTFORG_ORDINARY_CUSTOMER_TOKEN`. Current verified session was `role=owner`. |

These two tests must not be marked PASS without live evidence. Automated unit coverage for Owner-role gates and preference isolation remains in `tests/unit/`.

## Safety preserved

```text
MULTI_ACCOUNT_DISPATCH_ENABLED=false
MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false
OWNER_MAX_LOT=0.01
mandatory_stop_loss=true
```

P7 `planned_risk_pct=10.0000` must not be altered by follow-up work unless the customer changes it intentionally.

## Next phase

See `docs/architecture/MULTI_ACCOUNT_PHASE5_ELIGIBILITY.md` — preference-aware multi-account eligibility dry-run (LIVE dispatch/submit remain off).
