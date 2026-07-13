# QuantForg Final Go-Live Report

**Date:** 2026-07-13  
**Scope:** Public production launch — remaining P0 after successful boot  

---

## Launch Recommendation: **NO GO**

Application **boots and serves traffic**. Redis is correctly **`disabled`**.  
The single remaining launch blocker is **production Postgres connectivity** (`postgres: unhealthy`), caused by missing/incorrect Railway database configuration (fallback to `localhost`).

| Score | Value |
|-------|------:|
| Overall | **84** |
| Security | **94** |
| Performance | **98** |
| Reliability | **72** |
| Infrastructure | **58** |
| Scalability | **78** |

---

## Production validation (live)

| Check | Result |
|-------|--------|
| `GET /health/live` | **200** `alive` |
| `GET /api/v1/version` | **200** production |
| `GET /health` overall | **200** body `status: unhealthy` |
| `postgres` | **unhealthy** (~18 ms) |
| `redis` | **disabled** |

Latency signature matches **localhost:5432 connection refused** inside the Railway container, not Supabase pooler auth/SSL failure. See [`POSTGRES_PRODUCTION_FIX.md`](./POSTGRES_PRODUCTION_FIX.md).

---

## Stop conditions

| Condition | Status |
|-----------|--------|
| App boots (no ImportError) | **PASS** |
| Redis healthy or intentionally disabled | **PASS** (`disabled`) |
| Lighthouse Performance ≥95 (local) | **PASS** (98/100/100/100) |
| Playwright 7/7 (local) | **PASS** |
| Regression suites (local) | **PASS** |
| Production `postgres: healthy` | **FAIL** — operator must set Railway DSN |

---

## Root cause (Postgres)

1. Neither `DATABASE_URL` nor `SUPABASE_DB_PASSWORD` is effective on the Railway API service.  
2. Settings fall back to composed `POSTGRES_*` defaults → host **`localhost`**.  
3. Health probe `SELECT 1` fails in ~20 ms.  
4. Supabase Auth remains independent, so login can work while durable SQL is down.

---

## Required operator action (P0)

On Railway **API** service variables, set:

```text
DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<DB_PASSWORD>@aws-0-<REGION>.pooler.supabase.com:5432/postgres
```

(Session pooler, port **5432**.)  

**Or** set `SUPABASE_DB_PASSWORD` if `SUPABASE_URL` is already present (prefer explicit `DATABASE_URL` if region ≠ `eu-central-1`).

Then **redeploy** and confirm:

```bash
curl -sS https://quantforg-production.up.railway.app/health
```

Expected: `postgres.status == "healthy"` and overall `"healthy"`.

Full steps: [`POSTGRES_PRODUCTION_FIX.md`](./POSTGRES_PRODUCTION_FIX.md).

---

## Already green

- Circular import fix shipped (`HealthCheckPort` domain isolation) — Railway boots.  
- Redis optional reporting → `disabled` when `REDIS_URL` unset.  
- asyncpg SSL / DSN normalization for Supabase pooler (code ready; needs env).  
- Frontend Lighthouse + Playwright go-live suite.  
- Local API audit / pen-test harness previously green.  
- Startup diagnostics now emit `database_dsn_source` + `database_resolved_host` (no secrets) to confirm env wiring after redeploy.

---

## Critical / High / Medium / Low

### Critical
1. Set Railway `DATABASE_URL` (session pooler) or `SUPABASE_DB_PASSWORD` and redeploy until `/health` shows postgres healthy.

### High
1. Apply/confirm Supabase migrations on the same database as `DATABASE_URL`.  
2. After fix, re-check authenticated API paths that use durable persistence.

### Medium
1. Prefer Option A (`DATABASE_URL`) over hard-coded-region password composition.  
2. Optionally provision Redis later if shared rate-limit/cache is required.

### Low
1. Remove unused frontend packages when convenient.

---

## Checklists

### Railway
- [x] Service boots / liveness OK  
- [x] Redis intentionally disabled  
- [ ] `DATABASE_URL` or `SUPABASE_DB_PASSWORD` set  
- [ ] Logs: `database_resolved_host` = pooler host (not `localhost`)  
- [ ] `/health` → postgres healthy  

### PostgreSQL / Supabase
- [x] Pooler connectivity proven from operator/dev environment (prior validation)  
- [x] App SSL/DSN code supports Supabase pooler  
- [ ] Production env points at that DSN  
- [ ] Migrations applied  

### Redis
- [x] `disabled` in production health  

---

## Flip to **GO**

When live `/health` returns:

```json
{
  "status": "healthy",
  "dependencies": [
    { "name": "postgres", "status": "healthy" },
    { "name": "redis", "status": "disabled" }
  ]
}
```

→ Launch recommendation upgrades from **NO GO** → **GO**.
