# Railway / Production Startup Fix Report

**Date:** 2026-07-12  
**Scope:** Fix Railway 502 Bad Gateway after successful deploy (no trading/AI changes; `EXECUTION_ENABLED=false`).

## Root cause

Railway returned **502 Application failed to respond** because the process either:

1. **Crashed on import** under `APP_ENV=production` (Dockerfile default) when insecure defaults or `.env`-style `RELOAD=true` failed Settings validation, and/or
2. **Listened on the wrong port** — Dockerfile CMD hardcoded `--port 8000` while Railway injects **`$PORT`** and proxies only to that port.

Secondary issues that would keep the edge unhealthy or block probes:

- `ALLOWED_HOSTS` defaulted to `localhost` only (Railway hostname rejected by `TrustedHostMiddleware`).
- Redis connect failures could abort lifespan (now soft-fail).
- `/docs` disabled in production; no `GET /`; health only under `/api/v1`.

### Captured production import traceback (local reproduction)

```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
  Value error, RELOAD must be False in production
```

Without `.env` (Docker-like):

```text
Value error, SECRET_KEY must be replaced with a strong production value
```

With `SECRET_KEY` only:

```text
Value error, POSTGRES_PASSWORD must be replaced in production
```

(Platforms that only set `DATABASE_URL` hit this even with a valid DSN.)

## Why Railway returned 502

The edge proxy could not get a timely HTTP response from the container: either the ASGI process never stayed up (Settings ValidationError at `app = create_app()`), or it bound to **8000** while Railway forwarded traffic to **`$PORT`**.

## Fix implemented

| Area | Change |
|------|--------|
| Bind port | `scripts/docker-entrypoint.sh` uses `${PORT:-8000}`; Dockerfile `CMD ["./docker-entrypoint.sh"]` |
| Workers | Default `WORKERS=1` (Railway-friendly; override via `WEB_CONCURRENCY`) |
| Settings | `DATABASE_URL` / `REDIS_URL` overrides; skip `POSTGRES_PASSWORD` check when `DATABASE_URL` set; `docs_enabled`; `ALLOWED_HOSTS=*` default |
| Lifespan / DI | Redis, Supabase, MT5, persistence fail soft with warnings; app keeps serving |
| Health | Redis optional for overall status; Postgres probe skipped when `DURABLE_PERSISTENCE=false` / testing |
| Routes | `GET /`; health also mounted unprefixed (`/health`, `/health/live`, `/health/ready`); docs enabled via `DOCS_ENABLED` |
| Dockerfile | `RELOAD=false`, `EXECUTION_ENABLED=false`, `ALLOWED_HOSTS=*`, `DOCS_ENABLED=true`, liveness HEALTHCHECK on `/health/live` |

## Files changed

- `Dockerfile`
- `scripts/docker-entrypoint.sh` (new)
- `core/config/settings.py`
- `core/di/container.py`
- `app/main.py`
- `app/infrastructure/cache/redis_client.py`
- `app/infrastructure/health/unavailable.py` (new)
- `app/infrastructure/health/__init__.py` (new)
- `app/presentation/dependencies/services.py`
- `app/application/use_cases/get_health.py`
- `tests/unit/test_settings.py`
- `RAILWAY_STARTUP_FIX_REPORT.md` (this file)

## Local verification

```text
python -m uvicorn app.main:app  # APP_ENV=testing, DURABLE_PERSISTENCE=false
GET /              → 200
GET /health        → 200
GET /health/live   → 200
GET /health/ready  → 200
GET /docs          → 200
```

Startup log showed Redis unavailable as **warning**, process continued (`execution_enabled=False`).

## Tooling

- ruff: pass  
- black: pass  
- mypy: pass  
- pytest: pass (full suite)

## Docker verification

Docker CLI **not installed** on this host. Dockerfile + entrypoint are Railway-compatible (`$PORT`, tini, `python -m uvicorn`). Build on Railway / a Docker-capable host:

```bash
docker build -t quantforg:startup-fix .
docker run --rm -e PORT=8080 -e SECRET_KEY=... -e DATABASE_URL=... -p 8080:8080 quantforg:startup-fix
```

## Remaining risks

1. **`SECRET_KEY` must be set** in Railway (production validator still rejects insecure defaults).
2. **Postgres required for readiness** when `APP_ENV=production` and `DURABLE_PERSISTENCE=true` — provision Railway Postgres and set `DATABASE_URL`.
3. Without Redis, `/health` stays **200** (redis reported unhealthy but optional); features that need Redis will fail at call time.
4. Host Docker build not run here — first Railway redeploy after push is the live image verification.

## Required Railway variables

- `SECRET_KEY` (strong, no `change-me`)
- `DATABASE_URL` (or full `POSTGRES_*` with non-dev password)
- Optional: `REDIS_URL`, `ALLOWED_HOSTS=*`, `DOCS_ENABLED=true`, `EXECUTION_ENABLED=false`
