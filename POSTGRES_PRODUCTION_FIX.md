# PostgreSQL Production Fix

**Date:** 2026-07-13  
**Symptom:** `GET /health` → `postgres: unhealthy` while process is alive (`/health/live` = 200).  
**Redis:** correctly reports `disabled` (not the blocker).

---

## Root cause

Production Postgres health fails in **~15–25 ms**, which matches **TCP connection refused to `127.0.0.1:5432`** (local container loopback), not a remote Supabase auth/SSL failure.

| Failure mode | Typical latency | Matches prod (~18 ms)? |
|--------------|----------------:|:----------------------:|
| `localhost:5432` refused (no local Postgres in Railway container) | ~20 ms | **Yes** |
| Supabase direct host DNS failure (`db.<ref>.supabase.co`) | ~150–200 ms | No |
| Pooler reachable, bad password / SSL verify issues | ~1–2 s | No |

**Conclusion:** the API service is **not using a managed Postgres DSN**. It falls back to composed `POSTGRES_*` defaults (`POSTGRES_HOST=localhost`), so `SELECT 1` fails immediately.

Auth can still work because **Supabase Auth is separate** from the SQLAlchemy app database.

### Precedence (current code)

1. `DATABASE_URL` (aliases: `SUPABASE_DB_URL`)
2. Else `SUPABASE_DB_PASSWORD` + `SUPABASE_URL` → session pooler DSN  
3. Else `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` (defaults → **localhost**)

### Misleading log (pre-fix)

`database_url_configured=True` was previously true whenever `POSTGRES_HOST` had its default (`localhost`). Deploy logs after the diagnostic fix will show:

- `database_url_configured` — true only when `DATABASE_URL` is set  
- `database_dsn_source` — `DATABASE_URL` | `SUPABASE_DB_PASSWORD` | `POSTGRES_COMPOSED`  
- `database_resolved_host` — hostname only (no secrets)

If you still see `database_dsn_source=POSTGRES_COMPOSED` and `database_resolved_host=localhost` in Railway logs, the env vars below are still missing.

---

## Required Railway variable(s)

Set **one** of the following on the **API** Railway service (Variables).

### Option A (recommended): `DATABASE_URL`

Full session-mode pooler DSN from Supabase Dashboard → **Project Settings → Database → Connection string → Session pooler**.

```text
DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<DB_PASSWORD>@aws-0-<REGION>.pooler.supabase.com:5432/postgres
```

Example shape (secrets redacted):

```text
DATABASE_URL=postgresql://postgres.otqyhlmwaifokrczryrc:********@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
```

Optional (usually unnecessary — app auto-enables TLS for `*.supabase.co` / pooler hosts):

```text
# POSTGRES_SSL=true
# or append ?sslmode=require (stripped for asyncpg; enables TLS)
```

### Option B: compose from Supabase password

If `SUPABASE_URL` is already set on Railway:

```text
SUPABASE_DB_PASSWORD=<database password from Supabase Dashboard → Database>
```

App composes:

```text
postgresql://postgres.<ref>:<password>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
```

**Caveat:** region is currently hard-coded to `aws-0-eu-central-1` in composition. If your pooler host differs, prefer **Option A** with the exact host from the dashboard.

### Do not use (for this app)

| Avoid | Why |
|-------|-----|
| Transaction pooler `:6543` as default | Can break SQLAlchemy/asyncpg prepared statements; use **session** `:5432` |
| Direct `db.<ref>.supabase.co` from some networks | Host/DNS may be unavailable; prefer pooler |
| Railway Postgres plugin URL unless that is your intentional app DB | QuantForg durable schema targets the Supabase Postgres used by migrations |

---

## Exact value format (no secrets)

```text
postgresql://postgres.<PROJECT_REF>:<DB_PASSWORD>@aws-0-<REGION>.pooler.supabase.com:5432/postgres
```

Notes:

- User is `postgres.<PROJECT_REF>` for pooler (not bare `postgres`).
- Port **5432** = session mode (required for this stack).
- Do **not** commit the password. Store only in Railway Variables.
- Special characters in the password must be URL-encoded (`@` → `%40`, etc.).

---

## SSL / asyncpg

- App strips libpq-only query params (`sslmode`, `channel_binding`, …).
- For Supabase hosts, TLS is enabled with a runtime SSL context compatible with the pooler certificate chain.
- Private `*.railway.internal` hosts stay cleartext.

No code change required once a correct pooler `DATABASE_URL` is set.

---

## Migrations

After connectivity works:

1. Confirm Supabase SQL migrations for QuantForg are applied on the **same** database the DSN points to (`supabase/migrations/`).
2. Optional: `DATABASE_URL=... ./scripts/verify_migrations.sh` from a trusted operator machine.

Health only requires `SELECT 1`; missing tables do **not** mark postgres unhealthy, but app features will fail later without migrations.

---

## Verification steps

1. In Railway → API service → Variables: set Option A or B.  
2. Redeploy the API service.  
3. Open deploy logs → confirm:

   ```text
   database_dsn_source=DATABASE_URL   # or SUPABASE_DB_PASSWORD
   database_resolved_host=aws-0-....pooler.supabase.com
   ```

   Must **not** be `POSTGRES_COMPOSED` / `localhost`.

4. Probe:

   ```bash
   curl -sS https://quantforg-production.up.railway.app/health | python3 -m json.tool
   ```

5. Expected:

   ```json
   {
     "status": "healthy",
     "dependencies": [
       { "name": "postgres", "status": "healthy", "latency_ms": <number> },
       { "name": "redis", "status": "disabled", "latency_ms": <number> }
     ]
   }
   ```

6. If still unhealthy with pooler host in logs: rotate/verify DB password, confirm region/host from Supabase dashboard, ensure Railway egress can reach the pooler.

---

## Operator checklist

- [ ] `DATABASE_URL` **or** `SUPABASE_DB_PASSWORD` set on Railway API service  
- [ ] Session pooler (`:5432`), user `postgres.<ref>`  
- [ ] Password URL-encoded if needed  
- [ ] Redeploy completed  
- [ ] Logs show non-localhost resolved host  
- [ ] `GET /health` → `postgres: healthy`  
- [ ] Migrations applied on that database  
