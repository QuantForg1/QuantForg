# QuantForg Production Validation Report

**Date:** 2026-07-13  
**Deployment:** `https://quantforg-production.up.railway.app`  
**Commit under test (pre-fix):** `eb812ab`  
**Fixes pushed with this report:** see “Exact fixes applied”

---

## Verdict

| Layer | Result |
|-------|--------|
| Railway edge / public probes | **PASS** (`/`, `/health`, `/docs`, `/openapi.json` → 200) |
| Full FastAPI app boot | **PASS** (all routers + middleware + lifespan) |
| Authenticated API surface (ASGI parity audit) | **PASS 74/74** |
| Live production signup | **BLOCKED** by Supabase email rate limit (infra) |
| Production Postgres/Redis readiness | **DEGRADED** (operator TODO) |
| Production `/api/v1/ops/*` | **FAIL on live until redeploy** (fixed in code) |

---

## 1. Production Validation Report (live Railway)

### Confirmed healthy

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /` | 200 | `{"status":"ok"}` |
| `GET /health` | 200 | Body reports dependency health |
| `GET /api/v1/health` | 200 | |
| `GET /api/v1/health/live` | 200 | |
| `GET /api/v1/health/ready` | 200 | |
| `GET /api/v1/version` | 200 | |
| `GET /api/v1/metrics` | 200 | In-memory metrics (`persist=false`) |
| `GET /docs` | 200 | |
| `GET /openapi.json` | 200 | 78 paths |
| Unauthenticated protected routes | 401 | Correct `missing_token` |
| Invalid login | 401 | `invalid_credentials` |
| Invalid register payload | 422 | Email validation |

### Live production issues found

| Issue | Evidence | Severity |
|-------|----------|----------|
| Postgres dependency **unhealthy** | `/health` → postgres `unhealthy` (~17ms) | High (data plane) |
| Redis dependency **unhealthy** | redis probe unavailable / not connected | Medium (optional) |
| `/api/v1/ops/dashboard\|metrics\|alerts\|audit` → **500** | Persistence against unhealthy Postgres raised unhandled errors | High — **fixed in code** |
| `POST /api/v1/auth/register` → rate limited | Supabase: `email rate limit exceeded` mapped as 401 | Medium — **status mapping fixed**; quota is Supabase-side |
| Duplicate-email / rate-limit HTTP semantics | Always 401 via `AuthenticationError` | Medium — **fixed** (409 / 429) |

Live authenticated CRUD could not be completed on Railway because Supabase rejected new signups (`email rate limit exceeded`). Full authenticated coverage was completed via ASGI parity audit (same routers/middleware/use cases, FakeAuth + memory UoW).

---

## 2. Endpoints Tested

### Live Railway (unauthenticated / public)

- `GET /`, `/health`, `/api/v1/health`, `/health/live`, `/health/ready`
- `GET /api/v1/version`, `/api/v1/metrics`
- `GET /api/v1/ops/*` (failed 500 pre-fix)
- Auth negative paths: register validation, bad login, missing token
- OpenAPI: 78 documented paths enumerated

### ASGI production-parity audit (`scripts/prod_api_audit_local.py`) — 74 calls

Phases covered:

1. Auth — register, duplicate (409), login, me, refresh, logout, forgot-password, weak change-password (422)
2. Profile — get, patch, activity, avatar upload (201)
3. Settings — get/patch, devices, sessions
4. Notifications — list, preferences, preference patch
5. Organizations — create, invite
6. Brokers — CRUD, health, diagnostics; accounts; connect/validate/disconnect
7. MT5 — status, connect, account, symbols, order validate/calculate, disconnect
8. Strategy — evaluate, signals
9. Portfolio — portfolio/positions/orders/history (404 without MT5 session — correct)
10. Backtest — run, list, get by id
11. Paper — place order, positions, history, performance
12. Walkforward — run, results, get by id
13. Risk — check
14. Execution — check/submit (404 without MT5 — correct; execution disabled)
15. Ops — dashboard, metrics, alerts, audit
16. Metrics/version/health

---

## 3. Endpoints Passed

**ASGI audit: 74/74 passed** after fixes.

Notable correct behaviors verified:

- JWT session issue/refresh/logout
- Duplicate email → **409** (after fix)
- Weak password → **422**
- Broker create requires **admin/owner** (403 for trader)
- Pending broker rejects new accounts → **422**
- MT5 unavailable / no connection → **404** API error (no crash)
- Paper / backtest / walkforward / risk return schema-valid 200 responses
- Ops endpoints return 200 when persistence soft-fails

---

## 4. Endpoints Failed

### On live Railway (before redeploy of this fix set)

| Endpoint | Status | Cause |
|----------|--------|-------|
| `POST /api/v1/auth/register` | 401 | Supabase email rate limit |
| `GET /api/v1/ops/dashboard` | 500 | DB persist crash |
| `GET /api/v1/ops/metrics` | 500 | DB persist crash |
| `GET /api/v1/ops/alerts` | 500 | DB persist crash |
| `GET /api/v1/ops/audit` | 500 | Platform UoW crash |

### Found in ASGI audit (fixed)

| Endpoint | Was | Now |
|----------|-----|-----|
| Org/settings/broker/notification responses | Potential **500** via `dto.__dict__` on slotted dataclasses | Fixed with `dto_to_dict` |
| `POST /api/v1/broker-connections/validate` | **500** on bad login format | Mapped to **422** `ValidationError` |

---

## 5. Exact fixes applied

1. **`app/presentation/dto_mapping.py`** (+ all affected routers)  
   Replace `dto.__dict__` with `dto_to_dict()` for slotted dataclasses → prevents AttributeError HTTP 500 on orgs, settings, brokers, notifications, MT5, portfolio.

2. **`app/infrastructure/auth/supabase_auth.py`**  
   Map Supabase “rate limit” → `auth_rate_limited`.

3. **`app/presentation/middleware/error_handler.py`**  
   - `email_already_registered` → **409**  
   - `auth_rate_limited` → **429** (+ `Retry-After`)  
   - `email_not_verified` → **403**

4. **`app/application/use_cases/ops.py`**, **`alerting_service.py`**, **`audit_center.py`**  
   Soft-fail ops persistence so `/api/v1/ops/*` returns live data instead of 500 when Postgres is down.

5. **`app/application/use_cases/broker.py`**  
   Catch adapter `ValueError`/`OSError`/… in `ValidateBrokerUseCase` → `ValidationError` (422).

6. **`scripts/prod_api_audit_local.py`**  
   Repeatable full API audit harness.

CI: **300 passed, 2 skipped**.

---

## 6. Remaining TODO items (operator / infra)

1. **Redeploy** this commit to Railway so ops soft-fail + auth status codes + DTO mapping ship.
2. **Fix production Postgres** so `/health` reports postgres `healthy` (check `DATABASE_URL`, SSL, network, migrations / missing tables such as `system_metrics`).
3. **Provision Redis** (or accept degraded cache) — currently unhealthy/unavailable.
4. **Supabase Auth email rate limit** — raise quota or disable confirmation emails in Supabase project settings for staging; then re-run live register/login.
5. After signup works: re-run live authenticated audit against the public domain.
6. Confirm Railway variables: no manual `PORT=8000`; `ALLOWED_HOSTS` overridden by entrypoint `*`; `EXECUTION_ENABLED=false`.
7. Optional: add integration test that asserts slotted DTO responses never use `__dict__`.

---

## How to re-run

```bash
# Local parity (no Supabase rate limit)
poetry run python scripts/prod_api_audit_local.py

# Live public probes
curl -sS https://quantforg-production.up.railway.app/api/v1/health | jq
curl -sS https://quantforg-production.up.railway.app/api/v1/ops/dashboard | jq
```

After infra TODOs are cleared, live register → login → full phase matrix should match the 74/74 ASGI result.
