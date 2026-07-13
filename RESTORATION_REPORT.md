# QuantForg Full Application Restoration Report

**Date:** 2026-07-13  
**Context:** Railway networking confirmed healthy (`GET /` and `GET /health` → 200). Minimal/raw ASGI bypass removed; full FastAPI application restored.

---

## Summary

| Item | Before | After |
|------|--------|-------|
| `QF_MINIMAL` | `1` (default) → `app.raw_asgi:app` | **Removed** — always `app.main:app` |
| Middleware stack | Disabled entirely | **Re-enabled** (CORS, SecurityHeaders, Auth, Session, RequestContext, ProxyHeaders, AccessLog) |
| TrustedHost | Disabled | Skipped when `ALLOWED_HOSTS=*` (entrypoint forces this on Railway) |
| Routers | Not loaded (raw ASGI) | **19 routers** registered one-by-one via lazy import |
| Railway port/bind | `${PORT}` via entrypoint | **Unchanged** |
| Probe routes | `GET /`, `GET /health` | **200** with full app + middleware |

---

## Router-by-router startup audit

Each router module was imported individually. **No router failed.**

| # | Router | Module | Import | Mount |
|---|--------|--------|--------|-------|
| 1 | health | `app.presentation.routers.health` | OK | OK (`/api/v1` + unprefixed `/health`) |
| 2 | version | `app.presentation.routers.version` | OK | OK |
| 3 | auth | `app.presentation.routers.auth` | OK | OK |
| 4 | profile | `app.presentation.routers.profile` | OK | OK |
| 5 | settings | `app.presentation.routers.settings` | OK | OK |
| 6 | notifications | `app.presentation.routers.notifications` | OK | OK |
| 7 | organizations | `app.presentation.routers.organizations` | OK | OK |
| 8 | brokers | `app.presentation.routers.brokers` | OK | OK |
| 9 | broker_accounts | `app.presentation.routers.broker_accounts` | OK | OK |
| 10 | broker_connections | `app.presentation.routers.broker_connections` | OK | OK |
| 11 | mt5 | `app.presentation.routers.mt5` | OK | OK |
| 12 | execution | `app.presentation.routers.execution` | OK | OK |
| 13 | portfolio | `app.presentation.routers.portfolio` | OK | OK |
| 14 | risk | `app.presentation.routers.risk` | OK | OK |
| 15 | strategy | `app.presentation.routers.strategy` | OK | OK |
| 16 | backtest | `app.presentation.routers.backtest` | OK | OK |
| 17 | paper | `app.presentation.routers.paper` | OK | OK |
| 18 | walkforward | `app.presentation.routers.walkforward` | OK | OK |
| 19 | ops | `app.presentation.routers.ops` | OK | OK |

**First router failure:** `None` — all routers import and mount successfully.

Deploy logs will show:

```text
router_registered router=health prefix=/api/v1
...
router_registered router=ops prefix=/api/v1
router_registered router=health_unprefixed prefix=
router_registration_complete failed=[] first_failure=None
```

---

## First component that broke public access (historical)

During the Railway outage investigation, **no application router or middleware module failed at import or startup**. The symptoms were:

1. **Railway domain target port 8000** vs runtime `PORT=8080` — edge proxied to the wrong port (`x-railway-fallback: true`). Fixed in port audit (`bf19137`).
2. **`QF_MINIMAL=1` / `app.raw_asgi:app`** — intentional bypass that replaced the full app with a bare ASGI handler. Not a broken component; a diagnostic shim.
3. **Middleware stack disabled** — precaution during 502 investigation, not because middleware crashed on boot.

The **first isolated component** removed from the request path was the **entire full application** via `QF_MINIMAL` → `raw_asgi`. No individual router was the root cause.

---

## Middleware restoration

Re-enabled in order (last added = outermost):

| Component | Status | Notes |
|-----------|--------|-------|
| CORS | Enabled | Railway `*.up.railway.app` regex |
| TrustedHost | **Skipped** when `ALLOWED_HOSTS=*` | Entrypoint exports `ALLOWED_HOSTS=*` |
| SecurityHeaders | Enabled | |
| Authentication | Enabled | Does not block anonymous `/` or `/health` |
| Session | Enabled | |
| RequestContext | Enabled | |
| ProxyHeaders | Enabled | Trusts Railway `X-Forwarded-*` |
| AccessLog | Enabled | `incoming_request` in deploy logs |

### Surgical disable

Set `QF_DISABLED_COMPONENTS` (comma-separated) to skip a single component without reverting to minimal mode:

```text
QF_DISABLED_COMPONENTS=authentication,session
```

Valid names: `cors`, `trusted_host`, `security_headers`, `authentication`, `session`, `request_context`, `proxy_headers`, `access_log`, plus any router name (`mt5`, `execution`, etc.).

---

## Files changed

| File | Change |
|------|--------|
| `app/main.py` | Remove `QF_MINIMAL`/`raw_asgi` selector; lazy router registration; re-enable middleware |
| `docker-entrypoint.sh` | Always `app.main:app`; remove `QF_MINIMAL` branch |
| `Dockerfile` | Remove `QF_MINIMAL=1` |
| `tests/conftest.py` | Remove obsolete `QF_MINIMAL=0` override |

**Preserved (Railway fixes):** `docker-entrypoint.sh` `${PORT}` bind, `--proxy-headers`, `--forwarded-allow-ips='*'`, `ALLOWED_HOSTS=*`, `scripts/railway_self_check.py`, `railway.toml`.

**Not removed:** `app/raw_asgi.py`, `app/minimal_asgi.py` — kept for future diagnostics but no longer referenced by entrypoint or `app.main`.

---

## Verification

### Local (with `ALLOWED_HOSTS=*`)

```text
GET /          → 200 {"status":"ok"}
GET /health    → 200 (body includes dependency status)
GET /health/live → 200
```

### CI

```text
300 passed, 2 skipped
```

### Railway (after deploy)

Expect deploy logs:

```text
quantforg_entrypoint PORT=8080 HOST=0.0.0.0 APP_TARGET=app.main:app
trusted_host_middleware_skipped reason=allowed_hosts=*
middleware_stack_registered components=[...]
router_registration_complete failed=[] first_failure=None
startup_complete
self_check_ok status=200
Uvicorn running on http://0.0.0.0:8080
```

Public:

```text
GET https://<domain>/        → 200
GET https://<domain>/health  → 200
GET https://<domain>/docs    → 200 (if DOCS_ENABLED=true)
```

No `x-railway-fallback: true`.

---

## If a component fails after deploy

1. Check deploy logs for `router_registration_failed` or `application_startup_degraded`.
2. Add the failing name to `QF_DISABLED_COMPONENTS` in Railway variables.
3. Redeploy — `/` and `/health` remain available; only the named component is skipped.
4. Do **not** re-enable `QF_MINIMAL` or `raw_asgi`.
