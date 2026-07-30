# NOC Command Center — Production Release

**Date:** 2026-07-30T23:16Z  
**Trading logic modified:** No

## Git evidence

| Item | Value |
|------|-------|
| PR | [#42](https://github.com/QuantForg1/QuantForg/pull/42) — **MERGED** at `2026-07-30T23:12:46Z` |
| Merge commit | `1d415d9985bd872040505bec0857a3ac4379f39c` |
| `origin/main` | `1d415d9985bd872040505bec0857a3ac4379f39c` (verified) |
| NOC commits on main | `d639e28`, `1dab880`, `d9b26bf`, merge `1d415d9` |

## Railway (API) evidence

| Item | Value |
|------|-------|
| GitHub deployment id | `5683744151` |
| Environment | `QuantForg / production` |
| SHA | `1d415d9985bd872040505bec0857a3ac4379f39c` |
| Commit status | **success** — `QuantForg - QuantForg` / `Success - quantforg-production.up.railway.app` |
| Railway deployment id (from status URL) | `e1f7ad33-e646-4f71-808f-1d8dd4011f8e` |
| Production commit match | **YES** — status SHA == `origin/main` |

## Vercel (frontend) evidence

| Item | Value |
|------|-------|
| GitHub deployment id | `5683775500` |
| Environment | `Production` |
| Commit status | **success** — Deployment has completed |
| SHA | `1d415d9985bd872040505bec0857a3ac4379f39c` |

## Live verification (unauthenticated)

| Check | Result | Evidence |
|-------|--------|----------|
| `GET /api/v1/ite/ops/noc-command-center` | **401** `missing_token` | Endpoint deployed (was 404 pre-merge) |
| `POST /api/v1/ite/ops/noc-copilot` | **401** `missing_token` | Endpoint deployed |
| Unauthorized access | **Expected 401** | Confirmed |
| Authenticated 200 | **BLOCKED** | No `QUANTFORG_OWNER_TOKEN` in agent env |
| `https://www.quantforg.com/admin/noc` | **200**, `x-matched-path: /admin/noc` | Route present in production build |
| `https://www.quantforg.com/admin/operations` | **200**, `x-matched-path: /admin/operations` | Client-side redirect page shipped (router.replace → `/admin/noc`) |

## Post-deploy OpsAT

**File:** `docs/production/reports/noc_opsat/NOC_OPSAT_20260730T2316Z.json`  
**Verdict:** `NOC OPSAT NOT ACCEPTED`  
**Counts:** PASS=17 · FAIL=0 · BLOCKED=1

Only remaining blocker:

```text
prod_authenticated_telemetry
→ No QUANTFORG_OWNER_TOKEN / E2E_OWNER_TOKEN
→ Cannot prove authenticated GET 200 / copilot 200 against live production
```

## Remaining blocker (only)

Provide `QUANTFORG_OWNER_TOKEN` (or owner email/password) and re-run:

```bash
python scripts/opsat_noc_command_center.py
```

Expected after token:

- `GET /api/v1/ite/ops/noc-command-center` → **200**
- `POST /api/v1/ite/ops/noc-copilot` → **200** with grounded answer
