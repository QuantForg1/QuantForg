# Gateway import + auth header fixes (1.1.3)

Generated: `2026-07-30T15:45Z`  
Branch: `cursor/gateway-import-auth-fix-bc83`

## Runtime evidence (before this deploy)

`GET https://gateway.quantforg.com/health`:

- `gateway_version`: **1.1.1** (not yet on 1.1.2/1.1.3)
- `bridge_available`: **false**
- `probe`: **skipped**
- no `bridge_import_error` field (pre-diagnostic build)
- Auto-attach log: `ModuleNotFoundError: No module named MetaTrader5`
- Auth log: `gateway_auth_rejected received=<empty> header_source=missing`

Unauthenticated `GET /account` and `POST /session/attach` against the
public hostname return HTTP 401 `Invalid or missing gateway token`
(confirmed from this agent).

## 1) Why import still reports unavailable

`bridge_available` is **only** set after `import MetaTrader5` succeeds in the
**same Python process** that listens on port 8765.

`ModuleNotFoundError` is raised by the interpreter — it is not a fake message
and is not fixed by reinstalling into a different Python. Live host still
serves **1.1.1**; port 8765 is already occupied by that process.

1.1.3 logs on every failed import (never swallowed):

- `sys.executable` / `sys.version` / `sys.prefix`
- `site.getsitepackages()` / user site
- `importlib.util.find_spec("MetaTrader5")`
- `importlib.metadata.distribution("MetaTrader5")` (or its error)
- `importlib.invalidate_caches()` before retry

`/health` exposes `bridge_import_context` when import fails so operators can
compare the gateway process executable to `C:\Python314\python.exe` without
guessing.

## 2) Where the Authorization header disappears

Traced path:

```text
Frontend → Railway API (Supabase Bearer)
       → GatewayMT5Client._headers(auth=True)
       → Authorization + X-Gateway-Token (+ X-QuantForg-Gateway-Token)
       → FastAPI require_gateway_token
       → Gateway
```

Code bug fixed: Railway settings only accepted **`MT5_GATEWAY_CALLER_TOKEN`**.
If operators set **`MT5_GATEWAY_TOKEN`** (same name as Windows), the API built
**MockMT5Client** and never attached the shared secret. Concurrent probes /
scanners hitting protected routes then log
`header_source=missing` / `received=<empty>`.

Fixes:

- Accept `MT5_GATEWAY_TOKEN` as an alias for `mt5_gateway_caller_token`
- `GatewayMT5Client` always sends three auth headers when `auth=True`; refuses
  to send authenticated calls with an empty token
- Auth dependency also accepts `X-QuantForg-Gateway-Token` and logs
  `path` / `present_headers` / `user_agent` on reject (no hidden exceptions)
- Fallback ops helpers resolve caller token via
  `resolve_gateway_caller_token()` (CALLER_TOKEN **or** TOKEN)

## Operator steps (Windows + Railway)

1. Pull this branch; **kill** the process holding 8765; start
   `C:\Python314\python.exe -m services.mt5_gateway.main`
2. Confirm `/health` → `gateway_version=1.1.3`
3. If `bridge_available=false`, read `bridge_import_error` +
   `bridge_import_context.executable` (must match the pip target interpreter)
4. On Railway: set `MT5_GATEWAY_CALLER_TOKEN` (or `MT5_GATEWAY_TOKEN`) to the
   **exact** Windows `.env` token; redeploy API
5. Re-check authenticated routes with the shared token

Do **not** reinstall MetaTrader5 unless `bridge_import_context` shows
`find_spec=null` **and** `distribution_error` for that same executable.
