# Phase 4.1 — Risk Center Production Acceptance Closure

**Status:** IMPLEMENTATION COMPLETE — P7 persistence VERIFIED on Owner identity (2026-11-14); ordinary-customer Owner denial still BLOCKED  
**Closed (implementation):** 2026-11-10  
**Baseline SHA (Risk Center):** `d1c2bce3` (PR #224)  
**Frontend Production (at closure):** `e9df4614` / later `26a1438f` (Live Market follow-ups #225–#226)  
**Railway API (at closure probes):** `d1c2bce3` Online  
**Follow-up verification (2026-11-14):** Owner prefs still `10.0000` / `user_edit` on Railway `1e75cdf3`; frontend Production `55b8513d`  

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

## Production acceptance (credentials / identity)

| Test | Status | Evidence |
|---|---|---|
| P7 preference still 10% on Owner identity | **VERIFIED (2026-11-14)** | Owner `7d31c808-…` / `p7provider@gmail.com`: `/risk/preferences` → `planned_risk_pct=10.0000`, `persisted=true`, `source=user_edit`, `updated_at=2026-11-10`. See `docs/production/reports/phase2_ui/PHASE2_RELEASE_AND_P7_PREF_RESOLUTION.md`. |
| Apparent “P7 shows 20% default_copy” during Customer suite | **NOT A REGRESSION** | Different user `8ae4b619-…` (`role=trader`) correctly received unpersisted `default_copy`; historical 10% row is Owner-scoped (`user_prefix=7d31c808` in Phase 5.1 probe). |
| Explicit logout → fresh login persistence dance | **NOT RE-RUN** | Avoided Sign-out without disposable re-auth material; cross-session persistence already evidenced by unchanged DB/API row since 2026-11-10. |
| Ordinary non-owner Owner Policy denial (403) | **BLOCKED** | Still needs a dedicated ordinary (non-owner) customer token for a live 403 probe. Automated Owner-gate unit tests remain in `tests/unit/`. |

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
