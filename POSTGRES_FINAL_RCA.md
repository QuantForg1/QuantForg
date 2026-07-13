# PostgreSQL production health — final RCA

**Date:** 2026-07-13  
**Commit:** `9ab39313ee1b5bbef16aaa51b38322f0e8817613`  
**Service URL:** https://quantforg-production.up.railway.app  
**Railway project:** https://railway.com/project/76f9026d-362f-4e16-961d-44e7a090459a?environmentId=cb96aa83-7ace-470a-9e98-d52a1634a446

---

## Root cause

**Decision tree path B — process is not using `DATABASE_URL`.**

Production `GET /health` still reports `postgres = unhealthy` with **latency ≈ 24–50 ms**. That signature matches **TCP connection refused to `localhost:5432` inside the container**, not remote Supabase/Railway Postgres (typically hundreds of ms to seconds for auth/SSL/DNS failures).

The health probe already uses the **same** SQLAlchemy/`asyncpg` engine as the app (`Settings.database_url`). It does **not** ignore `DATABASE_URL` when that env var is present in the process.

Therefore: **`DATABASE_URL` is configured somewhere in Railway, but it is not visible to the running QuantForg API process**, so settings fall back to composed `POSTGRES_*` defaults (`POSTGRES_HOST=localhost`, port `5432`).

---

## Evidence

| Signal | Value | Interpretation |
|--------|--------|----------------|
| `GET /health` postgres | `unhealthy` | Probe `SELECT 1` fails |
| postgres `latency_ms` | 18–50 ms (stable across polls) | Local refuse / fast local fail — not remote RTT |
| redis | `disabled` | Expected when `REDIS_URL` unset |
| Health code path | `DatabaseManager.health_check` → shared engine | Uses `Settings.database_url` |
| Env var read by settings | `DATABASE_URL` / `SUPABASE_DB_URL` → `database_url_override` | Only if present in process env |
| Fallback when unset | `POSTGRES_COMPOSED` → `localhost:5432` | Matches latency signature |
| Misleading prior logs | `database_engine_started` logged `settings.postgres_host` | Field defaults to `localhost` even when `DATABASE_URL` is set — fixed in `9ab3931` |

### Exact health code path

```
GET /health
  → app/presentation/routers/health.py::health_check
  → HealthService.check()
  → GetHealthUseCase.execute()
  → PostgresHealthCheck.check()
  → DatabaseManager.health_check()
       → engine.connect() + SELECT 1
       → engine from Settings.database_url (DATABASE_URL when set)
       → driver: postgresql+asyncpg (not psycopg)
```

### What was ruled out (path A)

Path A (SSL / auth / URL encoding / asyncpg / pooler) applies only when logs show:

```text
database_dsn_source=DATABASE_URL
database_host=<remote-host>
```

Current latency evidence is incompatible with a successful parse of a remote pooler DSN. **Do not chase SSL/password until logs prove `DATABASE_URL` is the active source.**

---

## Startup diagnostics (shipped in `9ab3931`)

On engine start and on health success/failure, logs emit (never passwords):

| Field | Meaning |
|-------|---------|
| `database_dsn_source` | `DATABASE_URL` \| `SUPABASE_DB_PASSWORD` \| `POSTGRES_COMPOSED` |
| `database_host` | Hostname from resolved DSN |
| `database_port` | Port from resolved DSN (default 5432) |
| `database_sslmode` | `require` or `disable` (from asyncpg connect args) |
| `database_driver` | `postgresql+asyncpg` |

Also logs `engine_url_host` / `engine_url_port` / `engine_url_driver` from the live SQLAlchemy URL, and errors with `database_localhost_fallback_in_production` when production uses composed localhost.

**Operator confirmation (Railway dashboard → API service → Deploy Logs):**

After deploy of `9ab3931`, search for `database_engine_started`. Expected under path B:

```text
database_dsn_source=POSTGRES_COMPOSED
database_host=localhost
database_port=5432
database_sslmode=disable
database_driver=postgresql+asyncpg
```

> Note: This environment could not read Railway deploy logs via CLI (`railway` → Unauthorized). Confirm the five fields in the Railway UI. GitHub already reports deployment **success** for this SHA.

---

## Final fix (code)

Committed and pushed to `main` (`9ab3931`):

- `core/database/session.py` — safe DSN diagnostics; health uses shared engine; no secrets in logs
- `app/infrastructure/database/health.py` — documents shared-engine probe

**No business-logic / connection-behavior changes** (no SSL or pooler statement-cache changes in this commit).

Redeploy: triggered automatically by push to `main` (GitHub deployment `5419418745` → Railway production **success**).

---

## Why Railway is not exposing `DATABASE_URL` to this service

The operator reports `DATABASE_URL` is configured, but the **API process** behaves as if it is absent. That is an **environment/scope wiring** problem, not an application health-check bug.

Most likely causes (check in order):

1. **Wrong Railway service**  
   Variable set on the Postgres plugin service (or another service) but **not** on the QuantForg **API/web** service that serves `quantforg-production.up.railway.app`.

2. **Variable reference not expanded / not linked**  
   Value like `${{Postgres.DATABASE_URL}}` or a shared-variable reference that is not attached to this service → empty/unset at runtime → `POSTGRES_COMPOSED`.

3. **Wrong environment**  
   Variable present in a non-production environment, while the public domain is bound to environment `cb96aa83-7ace-470a-9e98-d52a1634a446`.

4. **Variable scope / shared-variable issue**  
   Project/shared variable exists but is not enabled for this service, or is overridden by an empty service-level `DATABASE_URL`.

5. **Name mismatch**  
   Typo or alternate name (`DATABASE_PRIVATE_URL`, `POSTGRES_URL`, etc.) without the aliases this app reads (`DATABASE_URL`, `SUPABASE_DB_URL`).

**Not the root cause:** health check ignoring `DATABASE_URL` when it is present in the process.

---

## Remaining operator actions

1. Open Railway → project above → **the service behind** `quantforg-production.up.railway.app` → **Variables**.
2. Confirm `DATABASE_URL` is listed **on that service** in the **production** environment and expands to a non-empty remote DSN (host ≠ `localhost` / `127.0.0.1`).
3. If missing: add/link it (Supabase session pooler recommended), e.g.  
   `postgresql://postgres.<REF>:<PASSWORD>@aws-0-<REGION>.pooler.supabase.com:5432/postgres`  
   URL-encode special characters in the password (e.g. `@` → `%40`).
4. Redeploy that service.
5. Confirm logs: `database_dsn_source=DATABASE_URL` and remote `database_host`.
6. Re-check `GET /health` → `postgres: healthy`.  
   Only if still unhealthy **with** `DATABASE_URL` + remote host, then investigate path A (SSL / auth / encoding / pooler).

---

## Status snapshot (post-deploy)

| Item | Result |
|------|--------|
| Commit SHA | `9ab39313ee1b5bbef16aaa51b38322f0e8817613` |
| CI | **success** — https://github.com/QuantForg1/QuantForg/actions/runs/29224978440 |
| Railway deployment | **success** (GitHub deployment status for production) |
| Final `/health` | `postgres: unhealthy` (~25–50 ms); `redis: disabled` |

**Launch blocker:** Postgres remains unhealthy until `DATABASE_URL` is actually injected into the API service process.
