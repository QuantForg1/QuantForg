# RC1 Release Report

Generated: 2026-07-31 (blocker resolution run)

## Final Recommendation

**NOT READY**

Evidence does not support LIMITED LIVE PILOT or FULL PRODUCTION.
No acceptance gate was bypassed. No merge to main. No production deploy.

---

## Blocker Status

### Blocker 1 — CI green (Lint / TypeCheck / Integration)

| Check | Evidence | Status |
|-------|----------|--------|
| Local Ruff (`app core tests`) | Clean after Black/ruff fixes | PASS (local) |
| Local Black | Clean | PASS (local) |
| Local MyPy (RC1 package) | Success | PASS (local) |
| Local unit (RC1) | 8 passed | PASS |
| Local integration | 106 passed, 2 skipped | PASS |
| Full unit suite (prior run) | 1417 passed | PASS |
| GitHub CI on PR #58 / #57 | Lint was failing on Black; fix pushed on `cursor/rc1-blocker-resolution-bc83` | PENDING CI re-run |
| Integration job in CI | Skips when Lint fails (`needs: [lint, typecheck, test]`) | Unblocked once Lint green |

**Remediation remaining:** Confirm GitHub Actions green on blocker-resolution PR after push.

### Blocker 2 — Deploy RC1 validation endpoints (HTTP 200)

| Check | Evidence | Status |
|-------|----------|--------|
| Local TestClient + OperatorUser | `docs/production/pre_live_evidence/rc1_endpoint_local_200.json` → **HTTP 200** | PASS (local wiring) |
| Production `GET /api/v1/ite/ops/rc1-production-validation` | **HTTP 404** (framework not on production tip) | FAIL |
| Staging host `quantforg-staging.up.railway.app` | Application not found | FAIL — **no staging environment** |
| Railway environments | Only `production` exists | FAIL |

**Remediation remaining:** Create Railway staging environment, deploy this branch, verify authenticated 200 on staging (then production only after gates).

### Blocker 3 — Authenticated infrastructure probes (no UNKNOWN)

Collected via `railway run -s QuantForg -- python scripts/collect_live_infra_evidence.py`
Artifact: `docs/production/pre_live_evidence/authenticated_infra_probes.json`

| Component | Observed status | Allowed for release? |
|-----------|-----------------|----------------------|
| Gateway (`gateway.quantforg.com`) | **DOWN** (HTTP 502 via Cloudflare) | NO |
| MT5 | **DISCONNECTED** (`mt5_use_mock=true`, gateway down) | NO |
| OMS | ENABLED (settings) / RUNTIME not in probe process | Incomplete live OMS health |
| AI | SETTINGS_ONLY (ITE runtime not in probe process) | Incomplete live AI health |
| API `/health` + `/health/status` | healthy; postgres healthy | PASS |
| Ops `services-health` | **401** without operator bearer | Auth still required for desk probe |

**No UNKNOWN invented as HEALTHY.** Residual DOWN / DISCONNECTED / SETTINGS_ONLY block release.

**Remediation remaining:** Restore Windows MT5 gateway / Cloudflare tunnel; capture operator-authenticated `services-health` with Gateway/OMS/MT5/AI all healthy.

### Blocker 4 — Database / migrations

| Check | Evidence | Status |
|-------|----------|--------|
| Apply migrations | **Not applied** (policy) | PASS (policy) |
| Staging verification | No staging environment | FAIL |
| Remote schema audit | `Network is unreachable` / `gaierror` to Supabase DB from agent egress | FAIL (unverified) |
| Repo inventory | 49 supabase up migrations; alembic `0001_baseline.py` | Recorded |
| Report | `docs/production/RC1_MIGRATION_REPORT.md` | Written |

**Remediation remaining:** From a network path that can reach Supabase, complete remote `schema_migrations` diff; apply only on staging after review.

### Blocker 5 — Staging paper / shadow + acceptance

| Check | Evidence | Status |
|-------|----------|--------|
| Staging deploy | No staging Railway environment | FAIL |
| Paper validation | Local pipeline with live health attached → NOT READY | Ran (not staging) |
| Shadow validation | Local pipeline with live health attached → NOT READY | Ran (not staging) |
| Acceptance gates | Infra DOWN / incomplete → **NOT READY** | FAIL |

Artifacts: `docs/production/RC1_VALIDATION_REPORT.md`, `docs/production/pre_live_evidence/rc1_*_result.json`

---

## What was fixed in this run

1. Black formatting for RC1 package files (CI Lint blocker).
2. Ruff import length fixes for RC1 runners.
3. Evidence collectors: live infra probe, migration audit, local endpoint 200 proof.
4. Hardening: acceptance refuses live recommendation when Gateway/OMS/MT5 unknown/down.

## What was explicitly NOT done

- No merge to `main`
- No automatic production deploy
- No database migrations applied
- No strategy / AI / threshold / weight / risk-logic changes

## Required path to READY FOR LIMITED LIVE PILOT

1. CI fully green on blocker-resolution PR (Lint + TypeCheck + Unit + Integration).
2. Create + deploy **staging** Railway environment with RC1 endpoints.
3. Authenticated staging `GET /ite/ops/rc1-production-validation` → 200.
4. Gateway HTTP 200 + MT5 connected (non-mock or approved demo path).
5. Operator `services-health` shows Gateway/OMS/MT5/AI healthy (no UNKNOWN/DOWN).
6. Staging paper then shadow validation with acceptance gates PASS.
7. Migration remote audit complete; staging migrations applied if needed; production still blocked until pilot approval.

Only after the above may recommendation change from **NOT READY**.
