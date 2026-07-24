# Railway Healthcheck Fix (RC1)

## Root cause

Uvicorn does not accept traffic until FastAPI **lifespan reaches `yield`**.
`await container.startup()` previously ran **before** yield and could block for minutes on:

- PostgreSQL pool warm (no connect timeout)
- MT5 gateway position recovery (sync HTTP, 60s timeouts + retries)
- ITE runtime wiring / heavy imports

Railway then failed at **Network → Healthcheck** (~4–5 minutes) even though Build/Deploy succeeded.

## Fixes (deployment only — no trading / AI / OMS logic changes)

1. **Lifespan yields immediately** after DI shell is created; infrastructure boots in a background task (`deferred-boot`). Tests still sync-await via `APP_ENV=testing` / `QF_SYNC_STARTUP=true`.
2. **MT5 position recovery** scheduled with `asyncio.to_thread` after listen (disable with `QF_RECOVERY_ON_STARTUP=false`).
3. **asyncpg connect timeout** default **10s**.
4. Instant probes: `GET /`, `/health`, `/healthz`, `/ready`, `/health/live`, `/health/ready` → `{"status":"ok"}`. Detailed deps moved to `/health/status`.
5. Startup timing logs: Route Registration / Database / Startup Total; warn if >5s.
6. Bind uses `PORT` / `HOST` from env (`0.0.0.0`); never prefer baked 8000 over Railway `PORT`.
7. `railway.toml` `healthcheckTimeout` reduced to **60s** (server should be healthy ≪10s after listen).

## Verify

```bash
# After deploy logs show: Health endpoint ready... / Listening on PORT ...
curl -sS https://$RAILWAY_PUBLIC_DOMAIN/health/live
# {"status":"ok"}
```
