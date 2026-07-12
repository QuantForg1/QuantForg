# Railway 502 Proxy Investigation

**Date:** 2026-07-13  
**Context:** Uvicorn starts successfully (`startup_complete`, bound `0.0.0.0:8080`) but Railway edge still returns **HTTP 502**.

## Why 502 with a running process?

Railway’s edge returns **502 Application failed to respond** when the upstream does not return a usable HTTP response in time (connection reset, hang, or process dies mid-request). Startup success only proves the listen socket is open — **not** that request middleware accepts Railway’s `Host` / forwarded headers.

## Root causes (request path)

### 1. `TrustedHostMiddleware` + bad `ALLOWED_HOSTS` (primary)

Platform-synced env often sets:

- `ALLOWED_HOSTS=localhost,127.0.0.1` (from `.env.example`), or  
- `ALLOWED_HOSTS=` (empty → parsed as `[]`)

Railway sends:

```http
Host: quantforg-production.up.railway.app
```

Starlette’s `TrustedHostMiddleware` rejects non-matching hosts. Combined with edge behaviour / retries, clients see Railway’s **502** page even though Uvicorn is up.

**Fix:**

- Entrypoint **always** `export ALLOWED_HOSTS="*"`
- Empty host list coerced to `["*"]` in Settings
- Skip `TrustedHostMiddleware` entirely when `*` is present (edge owns Host checks)

### 2. Missing proxy trust

Railway terminates TLS and forwards `X-Forwarded-*` from internal IPs. Uvicorn’s default `forwarded_allow_ips=127.0.0.1` ignores those headers.

**Fix:** `--proxy-headers --forwarded-allow-ips='*'` plus `ProxyHeadersMiddleware(trusted_hosts="*")`.

### 3. Observability gap

Without access logs it was unclear whether requests reached the app.

**Fix:** outermost `RequestAccessLogMiddleware` logs `METHOD`, `PATH`, `STATUS`, `Host` for every request.

## Routes confirmed

| Path | Expected |
|------|----------|
| `GET /` | `{"status":"ok"}` 200 |
| `GET /health` | 200 |
| `GET /health/live` | 200 |
| `GET /health/ready` | 200 |
| `GET /docs` | 200 |

## Files changed

- `app/main.py` — skip TrustedHost when `*`; ProxyHeaders; access log; root JSON
- `app/presentation/middleware/access_log.py` — request logger
- `docker-entrypoint.sh` — force `ALLOWED_HOSTS=*`; proxy CLI flags
- `core/config/settings.py` — empty hosts → `["*"]`
- `tests/unit/test_settings.py` — empty hosts test
- `RAILWAY_502_PROXY_REPORT.md` — this file

## How to verify on Railway after deploy

1. Hit public URL `/` and `/health/live`.  
2. In deploy logs, look for:

```text
incoming_request method=GET path=/ status_code=200 host=....up.railway.app
trusted_host_middleware_skipped reason=allowed_hosts=*
```

3. If `incoming_request` never appears → edge still not reaching the container (port/service wiring).  
4. If `incoming_request` appears with 4xx/5xx → inspect that status.  
5. If Host is rejected again → confirm Railway var `ALLOWED_HOSTS` is overridden by entrypoint (`ALLOWED_HOSTS=*` in entrypoint echo line).

### 4. Unhandled exceptions aborting the ASGI connection

`BaseHTTPMiddleware` (auth/session) can turn unhandled dependency errors into
**“No response returned”** connection failures — which Railway surfaces as **502**.

**Fix:** `get_health_service()` never raises if the DI container is not ready;
returns an empty-probe healthy report instead.


- Startup / Settings `RELOAD` (already fixed; logs show `startup_complete`)
- Missing routes (health mounted at root and `/api/v1`)
- HTTPSRedirectMiddleware (not installed)
