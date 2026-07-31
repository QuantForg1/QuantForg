# Final Pre-Live Checklist — Evidence Log

**Verdict: NOT READY — STOP deployment**

No merge to main. No production go-live. No automatic migrations.

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Merge candidate PRs after code review | **BLOCKED** | Open drafts (#57/#56/#55/#54–#49) have Lint and/or Type Check failures; Integration Tests skipped in CI. None merged. |
| 2 | Unit / integration / regression tests | **PARTIAL** | Local unit: **1417 passed**. Integration: **106 passed, 2 skipped**. CI Integration job currently **skipping**. |
| 3 | Staging DB migrations | **NOT APPLIED** | Forbidden by mission. QuantForg Supabase `otqyhlmwaifokrczryrc` permission denied. |
| 4 | No new pending migrations verified | **UNVERIFIED** | Repo has 49 supabase up migrations + alembic baseline; remote drift unknown. |
| 5 | Deploy to staging | **NOT DONE** | Vercel MCP needsAuth; no staging deploy performed. |
| 6 | Live evidence | **PARTIAL** | Process `/health` OK; postgres healthy; Gateway/OMS/MT5/AI **UNKNOWN** (401). RC1 route **404** on prod. |
| 7 | RC1 paper | **RAN** | Local pipeline with live probes attached. |
| 8 | RC1 shadow | **RAN** | Local pipeline with live probes attached. |
| 9 | Acceptance gates all pass | **FAIL** | Infra UNKNOWN → **NOT READY**. |
| 10 | Release PR / prod recommend | **NOT OPENED** | Failure report opened instead. |

## Live public probes (Railway production)

- `GET /health` → 200 `{"status":"ok"}`
- `GET /api/v1/health` → 200
- `GET /api/v1/ready` → 200
- `GET /api/v1/health/status` → healthy; postgres healthy; redis disabled; env=production
- Ops health (`/ite/ops/services-health`, PVM, RC1 telemetry) → **401 missing_token**
- `GET /ite/ops/rc1-production-validation` → **404** (framework not on production tip)

## Artifacts

- `docs/production/RC1_VALIDATION_REPORT.md`
- `docs/production/RC1_PRE_LIVE_FAILURE_REPORT.md`
- `docs/production/pre_live_evidence/`
