# Windows MT5 Gateway update — PR #295

The existing gateway on the Windows PC (`gateway.quantforg.com`, port 8765, `services.mt5_gateway.main`) is updated in place. No new VPS and no new service.

## Why the gateway needs updating

`services/mt5_gateway/order_guard.py` imports the owner limits from `app/domain/institutional_trading/owner_live_limits.py`. Until the PC's checkout is updated, the gateway's last-line guard still allows 20% per trade. PR #295 also moves the per-trade check ahead of the book check, so a rejection reports the correct reason.

`__version__` stays `1.2.0` in this PR. Verify the update by commit SHA, not by version.

## Order of release

1. Merge PR #295. Railway deploys the backend.
2. Run `apply.sql` (data change G1).
3. Update the gateway (this document).

Updating the gateway last is safe. Its guard can only make the backend's decisions stricter, never looser.

## Pre-checks (stop if any one fails)

- No open position on the Weltrade account: MT5 terminal → Trade tab is empty.
- No pending order is waiting to be sent.
- The backend is already on the merged SHA. Check `GET /api/v1/health` on Railway.
- The owner has decided the LIVE state for the restart window. A restart briefly drops the gateway connection. The backend fails closed and sends nothing while the gateway is down.

## 1. Find the checkout the running gateway uses

The live repo root is not confirmed. The supervisor logs in `C:\QuantForg-Workspace\QuantForg` stop around 27 Oct. In PowerShell (Admin):

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'services\.mt5_gateway\.main' } |
  Select-Object ProcessId, ExecutablePath, CommandLine
Get-ScheduledTask -TaskName QuantForgMT5Gateway | Select-Object -ExpandProperty Actions
```

The `.venv\Scripts\python.exe` path in `ExecutablePath` gives the repo root, which is the parent of `.venv`. Set it once:

```powershell
$Root = '<repo root found above>'
cd $Root
git rev-parse HEAD          # record as PREVIOUS_SHA (rollback target)
git status --porcelain      # must be empty; stop if not
```

## 2–3. Deploy the merged commit and restart

From `$Root` (PowerShell as Administrator):

```powershell
.\deploy\mt5_gateway\deploy_main_gateway.ps1 -TargetSha <MERGED_SHA>
```

The script (fixed in this PR):

- deploys exactly `<MERGED_SHA>`, detached, and checks that `HEAD` matches it;
- refuses a dirty tree;
- refuses to restart while there is an open position or a pending order. It checks once before the checkout and again right before the restart;
- prints the owner limits it loaded (expected `9.0 25.0 1.50 0.45`);
- restarts through `supervise_gateway.ps1 -Once`;
- verifies `/health`, `/account`, `/quotes/XAUUSD` and `/candles/XAUUSD`;
- writes `previous_commit` to `docs\production\reports\oat_v71\deploy_main_gateway_verify.json`.

PR #295 adds no new dependencies, so `pip install` is not needed.

## 4. Verify

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health        # mt5 connected, gateway_version 1.2.0
Invoke-RestMethod http://127.0.0.1:8765/account       # server Weltrade-Real, expected login
Invoke-RestMethod http://127.0.0.1:8765/quotes/XAUUSD # fresh bid/ask, spread
```

Then check from Railway that `gateway_http_response path=/account status_code=200` appears again in the logs.

## Rollback

```powershell
.\deploy\mt5_gateway\deploy_main_gateway.ps1 -TargetSha <PREVIOUS_SHA>
```

The rollback restores the old guard (20%). If the backend is also rolled back, roll back the gateway with it.
