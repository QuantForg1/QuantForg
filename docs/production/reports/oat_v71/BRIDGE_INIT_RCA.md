# Gateway bridge init RCA — bridge_available=false on 1.1.1

Generated: `2026-07-30T15:05Z`  
Branch: `cursor/v7-1-acceptance-evidence`

## Verified live symptom

`GET https://gateway.quantforg.com/health`:

- `gateway_version`: `1.1.1`
- `mt5.connected`: `false`
- `mt5.session_mode`: `none`
- `mt5.bridge_available`: `false`
- `mt5.probe`: `skipped`
- `mt5.capability_note`: `MetaTrader5 bridge unavailable — capabilities NOT_SUPPORTED`

Broker UI **"Gateway initialize failed"** maps to Railway
`weltrade_integration` → `adapter.initialize()` →
`GatewayMT5Client.initialize()` which returns `False` when
`health.bridge_available is False`
(`app/infrastructure/brokers/mt5/gateway_client.py`).

Port **8765 already in use** (`WinError 10048`) means a gateway process is
already listening; starting a second `py -m services.mt5_gateway.main` fails.
The live process is the one answering `/health`.

## Bridge technology (repo fact)

| Mechanism | Used? |
|---|---|
| MetaTrader5 **Python package** | **YES** — `LiveMT5Bridge` in `services/mt5_gateway/runtime.py` |
| Expert Advisor (`.ex5`) | **NO** — zero `.mq5`/`.ex5` in repository |
| Custom DLL bridge | **NO** |
| Named pipes / custom sockets to MT5 | **NO** (gateway HTTP/WS is QuantForg API only) |

`LiveMT5Bridge.__init__` does:

```python
import MetaTrader5 as mt5
```

`bridge_available` is `self._mt5 is not None`.  
If import fails, `_import_error` is set and **no** `initialize()` / attach can run.

## Failing code path

1. Process start → `MT5GatewayRuntime()` → `LiveMT5Bridge()`
2. `import MetaTrader5` fails in **that** Python interpreter
3. `bridge.available == False`
4. `health()` returns early with `probe=skipped`, `connected=false`
5. Auto-attach cannot run usefully (`require()` raises package unavailable)
6. Railway/UI reports initialize failed

This is **not** an MT5 terminal login problem by itself: terminal can be logged
into Weltrade while the **Python process serving :8765** still lacks a working
`MetaTrader5` import.

## No Expert Advisor required

Do not install or attach any `.ex5` for QuantForg gateway. The official
MetaTrader5 Python API talks to the running terminal IPC after
`MetaTrader5.initialize()`.

## Operator recovery (Windows host)

Run in elevated PowerShell on the production host:

```powershell
# 1) Which process owns 8765?
Get-NetTCPConnection -LocalPort 8765 -State Listen |
  Select-Object OwningProcess -Unique |
  ForEach-Object { Get-Process -Id $_.OwningProcess | Format-List Id,ProcessName,Path }

# 2) Does THAT interpreter import MetaTrader5?
# Replace with the Path from step 1 if different from Python314:
& "C:\Python314\python.exe" -c "import MetaTrader5 as m; print('OK', m)"

# 3) If import fails, install into the same interpreter:
& "C:\Python314\python.exe" -m pip install --upgrade MetaTrader5

# 4) Stop the listener, start ONE gateway instance from the repo:
Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue |
  ForEach-Object { taskkill /F /PID $_.OwningProcess }
cd "C:\Users\P7 PROVIDER\QuantForg"
& "C:\Python314\python.exe" -m services.mt5_gateway.main

# 5) Verify (expect bridge_available=true, then attach if needed):
Invoke-RestMethod http://127.0.0.1:8765/health | ConvertTo-Json -Depth 6
```

If `bridge_available` becomes true but `connected` is still false while the
terminal is logged in, then (with token from `.env`):

```powershell
Invoke-RestMethod -Method POST http://127.0.0.1:8765/session/attach `
  -Headers @{ Authorization = "Bearer <MT5_GATEWAY_TOKEN>" } -ContentType "application/json" -Body "{}"
```

## Code change in this investigation

`/health` now includes `bridge_import_error` when `bridge_available=false` so
the live import failure text is visible without a gateway token.

## Success criteria (not yet met)

Do **not** claim recovery until live `/health` shows:

- `connected=true`
- `bridge_available=true`
- `session_mode` != `none`
