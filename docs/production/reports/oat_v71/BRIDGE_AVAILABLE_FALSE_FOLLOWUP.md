# Bridge available=false after MetaTrader5 installed — follow-up RCA

Generated: `2026-07-30T15:25Z`

## Runtime evidence (live)

`GET https://gateway.quantforg.com/health` at investigation time:

- `gateway_version`: `1.1.1`
- `bridge_available`: `false`
- `connected`: `false`
- `probe`: `skipped`
- **`bridge_import_error` field absent**

Absence of `bridge_import_error` proves the live process is still running a
build **before** commit `530e016` (which added that field). Version string
`1.1.1` alone does not prove latest diagnostics code is loaded.

No gateway `*.out.log` / `*.err.log` files are present in git for this host
run, so log lines cannot be quoted from the repository. Conclusions below are
from code paths that define `bridge_available` plus the live JSON above.

## Where `bridge_available` becomes false

Only here (`LiveMT5Bridge`):

```text
available  <=>  (self._mt5 is not None)
_mt5 set only after successful `import MetaTrader5`
```

**`MetaTrader5.initialize()` is never called when `bridge_available=false`.**
`probe=skipped` is the health early-return for import failure, not an
initialize failure.

So a successful interactive `import MetaTrader5` in a new shell does **not**
update an already-running gateway process that imported (and failed) at
startup — unless the process re-imports.

## Repository root cause fixed

`LiveMT5Bridge` previously imported MetaTrader5 **once** in `__init__` and
never retried. If the package became importable after process start, health
kept reporting `bridge_available=false` forever.

Fix in gateway **1.1.2**:

- `_ensure_module()` retries import on demand (`available` / `require`)
- Clears stale `sys.modules` entries before retry
- Logs `mt5_bridge_import_ok` / `mt5_bridge_import_failed`
- `initialize()` logs begin/end and records `last_error()`
- `/health` exposes `bridge_import_error` or `bridge_initialize_error`

## What the operator must do (environmental, not “pip install again”)

1. **Restart the single gateway process** on port 8765 so it loads **1.1.2**
   (pull `cursor/v7-1-acceptance-evidence`, kill listener, start
   `C:\Python314\python.exe -m services.mt5_gateway.main`).
2. Re-check `/health`:
   - If `bridge_available=true` → import works in-process; then attach if needed.
   - If still false → read **`bridge_import_error`** (actual exception text).
   - If import ok but attach fails → read **`bridge_initialize_error`** /
     logs `mt5_initialize_end ... last_error=...`.

Do not reinstall MetaTrader5 unless `bridge_import_error` explicitly shows
`ModuleNotFoundError`.

## Success not claimed

Live gateway has **not** been verified at `connected=true` after this change.
