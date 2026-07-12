# Deployment

**Release:** QuantForg v1.0.0-rc.1  

## Prerequisites

- Python **3.13** (CI and Dockerfile aligned)  
- Poetry 1.8.x  
- PostgreSQL 15+ (or Supabase Postgres)  
- Redis 7+  
- Optional: Supabase project (URL + anon + service role keys)  

## Environment variables

Copy `.env.example` → `.env`. Critical keys:

| Variable | Purpose | Production note |
|----------|---------|-----------------|
| `APP_ENV` | `development` / `testing` / `staging` / `production` | Must be `production` in prod |
| `APP_VERSION` | Semantic version | `1.0.0-rc.1` |
| `SECRET_KEY` | App crypto / tokens | Must not contain `change-me` |
| `POSTGRES_*` | Database | Strong password; no `dev_password` |
| `REDIS_*` | Cache / health | Prefer auth + TLS where available |
| `SUPABASE_*` | Auth + PostgREST | Never commit real keys |
| `MT5_USE_MOCK` | Mock MT5 client | `true` for RC unless Windows live terminal |
| `EXECUTION_ENABLED` | Live `order_send` gate | **Must remain `false` for GA** |
| `DURABLE_PERSISTENCE` | Postgres UoWs vs memory | `true` outside testing |
| `DEBUG` / `RELOAD` | Dev helpers | Must be `false` in production |

Production validators in `core/config/settings.py` reject insecure defaults when `APP_ENV=production`.

## Container deploy

```bash
docker build -t quantforg:1.0.0-rc.1 .
docker run --env-file .env -p 8000:8000 quantforg:1.0.0-rc.1
```

Image uses `tini` + `uvicorn` (4 workers). HEALTHCHECK: `GET /api/v1/health`.

## Migrations

Schema truth: `supabase/migrations/*.sql` (reversible downs in `supabase/migrations/down/`).

Apply ups in timestamp order through Supabase CLI or your migration runner. Latest RC1 ops migrations:

- `20260712154000_operations_platform.sql`  
- `20260712154100_operations_platform_rls.sql`  

Alembic holds a baseline only; do not treat Alembic as the primary migration path for feature tables.

## Rollback plan

1. Stop new app traffic (scale to zero / drain).  
2. Redeploy previous image tag.  
3. Apply matching `*.down.sql` for migrations applied only by the failed release (reverse timestamp order).  
4. Verify `/api/v1/health/ready` and `/api/v1/health/live`.  
5. Confirm `EXECUTION_ENABLED=false`.  

Details: `BACKUP_RECOVERY.md`.

## Startup checks

On process start (`app/main.py` lifespan):

1. Load settings + structured logging  
2. Construct DI `Container`  
3. `container.startup()` — Postgres, Redis, feature services, Mock MT5  

Fail-fast if Redis/Postgres cannot connect when health probes run.

## Health checks

| Probe | Path | Meaning |
|-------|------|---------|
| Liveness | `GET /api/v1/health/live` | Process up |
| Readiness | `GET /api/v1/health/ready` | Postgres + Redis OK |
| Aggregate | `GET /api/v1/health` | Same deps; 503 if unhealthy |
| Metrics | `GET /api/v1/metrics` | Ops metrics snapshot |

Orchestrators should gate traffic on **ready**, restart on **live** failure.

## CI/CD

`.github/workflows/ci.yml` runs ruff, black, mypy, pytest on `main`/`develop`. Poetry resolves from `pyproject.toml` (lockfile generation recommended before GA).

## RC1 deployment constraints

- Do not set `EXECUTION_ENABLED=true`.  
- Prefer `MT5_USE_MOCK=true`.  
- Feature UoWs are largely in-memory in the default container wiring — treat durable feature persistence as a GA follow-up (see `PRODUCTION_READINESS_REPORT.md`).
