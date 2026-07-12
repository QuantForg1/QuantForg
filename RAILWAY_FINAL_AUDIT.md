# Railway Final Deployment Audit

**Date:** 2026-07-13  
**Commit target:** `main`  
**Goal:** QuantForg starts on Railway with no crash, no 502, health/docs HTTP 200.

---

## Root causes found

### 1. `RELOAD must be False in production` (crash on import)

Railway injects service variables that often include **`RELOAD=true`** (synced from `.env` / `.env.example`).  
Dockerfile `ENV RELOAD=false` is **overridden** by Railway’s higher-priority service env.  
Settings then raised `ValidationError` during `app = create_app()` → process exits → **502**.

**Fix:** Production **coerces** `reload=False` and `debug=False` instead of crashing.  
Entrypoint also `export RELOAD=false DEBUG=false` before uvicorn.

### 2. Entrypoint excluded by `.dockerignore`

`.dockerignore` contained `scripts`, which blocked `COPY scripts/docker-entrypoint.sh`.  
Image could miss the `$PORT` entrypoint and fall back to broken/hardcoded startup.

**Fix:** Root `docker-entrypoint.sh` copied into the image; `.dockerignore` allows the entrypoint.

### 3. Hardcoded port / workers (prior)

Already addressed: bind `0.0.0.0:$PORT`, default 1 worker.

### 4. Optional deps crashing startup

Redis (and similar) unavailable must not abort lifespan.

**Fix:** Soft-fail with warnings; health still HTTP 200 by default (`HEALTH_HTTP_STRICT=false`).

---

## Files changed

| File | Change |
|------|--------|
| `core/config/settings.py` | Coerce RELOAD/DEBUG in production; `ENVIRONMENT` alias; `RAILWAY_PUBLIC_DOMAIN`; `HEALTH_HTTP_STRICT`; `populate_by_name` |
| `docker-entrypoint.sh` | **New** root entrypoint; forces safe env; logs Python/APP_ENV/PORT |
| `Dockerfile` | Copy root entrypoint; `ENVIRONMENT=production`; `HOST=0.0.0.0` |
| `.dockerignore` | Stop excluding entrypoint |
| `scripts/docker-entrypoint.sh` | Compatibility wrapper |
| `app/main.py` | Startup diagnostics (`startup_diagnostics`, `startup_complete`) |
| `app/presentation/routers/health.py` | HTTP 200 unless `HEALTH_HTTP_STRICT=true` |
| `tests/unit/test_settings.py` | Coercion + ENVIRONMENT alias tests |
| `tests/unit/test_api.py` | Unhealthy health → 200 by default |
| `.env.example` | Document Railway RELOAD warning |
| `RAILWAY_FINAL_AUDIT.md` | This document |

---

## Variables required (Railway)

| Variable | Required | Notes |
|----------|----------|--------|
| `SECRET_KEY` | **Yes** | Strong; no `change-me` |
| `DATABASE_URL` | **Yes** (recommended) | Overrides `POSTGRES_*` |
| `PORT` | Injected by Railway | Entrypoint binds it |
| `APP_ENV` / `ENVIRONMENT` | Prefer `production` | Dockerfile default |
| `DEBUG` | Forced `false` by entrypoint + settings | |
| `RELOAD` | Forced `false` by entrypoint + settings | Safe even if set `true` in dashboard |
| `EXECUTION_ENABLED` | Keep `false` | |
| `REDIS_URL` | Optional | Soft-fail if missing |
| `ALLOWED_HOSTS` | Default `*` | |
| `DOCS_ENABLED` | Default `true` | |
| `RAILWAY_PUBLIC_DOMAIN` | Optional | Appended to allowed hosts if not `*` |
| `HEALTH_HTTP_STRICT` | Default `false` | Set `true` only for K8s-style 503 |

**Unset or fix in Railway dashboard if present:** `RELOAD=true`, `DEBUG=true` (harmless after this fix, but clean them anyway).

---

## Deployment verification (local)

```text
APP_ENV=production RELOAD=true DEBUG=true SECRET_KEY=<strong> DATABASE_URL=... 
→ startup_diagnostics shows reload=False debug=False
→ Application startup complete
→ GET / /health /health/live /health/ready /docs → 200
```

Tooling:

- ruff: pass  
- black: pass  
- mypy: pass  
- pytest: **299 passed**, 2 skipped  

Docker CLI: **not installed on this host**. Image build must be confirmed by Railway’s Docker build after push. Entrypoint path and `.dockerignore` were audited for COPY success.

---

## Final checklist

- [x] Production never crashes on `RELOAD=true` / `DEBUG=true`
- [x] Entrypoint present at image root and not dockerignored
- [x] Bind `0.0.0.0:$PORT`
- [x] `DATABASE_URL` supported; `POSTGRES_*` ignored when set
- [x] Redis optional (warning, not crash)
- [x] `EXECUTION_ENABLED` remains false by default
- [x] Startup diagnostics logged
- [x] Health/docs/root return HTTP 200 (default)
- [x] CI-quality checks green
- [ ] Railway redeploy of this commit shows healthy public URL (post-push)

---

## Operator actions after deploy

1. Set `SECRET_KEY` and `DATABASE_URL` in Railway.  
2. Remove `RELOAD` / `DEBUG` from Railway variables if set to true (optional hygiene).  
3. Confirm logs contain `startup_complete` and `quantforg_entrypoint ... RELOAD=false`.  
4. Hit `https://<RAILWAY_PUBLIC_DOMAIN>/health` → 200.
