# Windows MT5 gateway: recovery and update (16 Nov 2026)

## Which commit the gateway must run

| | SHA |
|---|---|
| Production backend (Railway deployment `7e649d4e`, SUCCESS) | `9b52ce67f1999d2543361ac5c9df60f9c10c3e7a` |
| **Gateway target** | **`9b52ce67f1999d2543361ac5c9df60f9c10c3e7a`** (same as the backend) |

How the target was verified:
- Loading `services.mt5_gateway.main` imports 153 `app.*` modules, including `owner_live_limits`, `runtime_policy` and `gold_only`.
- Between `9543ecbb` (#295, which introduced the 9/25/1.5/0.45 limits) and `9b52ce67`, none of those modules and nothing under `services/mt5_gateway` changed. The gateway's code is therefore identical at both commits.
- Running the backend's exact SHA keeps the two sides byte-identical.

The previously suggested `70328f76` holds the same gateway code, but use `9b52ce67` for exact parity.

## Current state (before restart)

- `/health` reports the last heartbeat at 10:18:37 UTC on 16 Nov, so the heartbeat thread has been stalled for more than 7 hours.
- `/history/deals` times out (60–140 s).
- `/account` and `/positions` still answer.
- Production is flat: `/positions` returned `[]` and there are no open journal rows.
- LIVE (DB) is ENABLED, and the ITE is not trading: daily P/L is untrusted, so it fails closed.

## Procedure (PowerShell as Administrator on the Windows PC)

1. **Find the checkout the running gateway uses.**

   ```powershell
   Get-CimInstance Win32_Process |
     Where-Object { $_.CommandLine -match 'services\.mt5_gateway\.main' } |
     Select-Object ProcessId, ExecutablePath, CommandLine
   ```

   `$Root` is the folder that contains `.venv\Scripts\python.exe`.

   ```powershell
   cd $Root
   git status --porcelain   # must print nothing
   ```

2. **Check that the account is flat in the MT5 terminal.** The Trade tab must show no open positions and no pending orders. If anything is open, stop and wait.

3. **Deploy and restart.**

   ```powershell
   .\deploy\mt5_gateway\deploy_main_gateway.ps1 -TargetSha 9b52ce67f1999d2543361ac5c9df60f9c10c3e7a
   ```

   The script:
   - checks `/positions` and `/orders` before the checkout and again right before the restart, and refuses if anything is open;
   - refuses a dirty tree;
   - checks out exactly that SHA, detached;
   - prints `owner_limits=9.0 25.0 1.50 0.45`;
   - restarts through `supervise_gateway.ps1 -Once`;
   - verifies `/health`, `/account`, `/quotes/XAUUSD` and `/candles/XAUUSD`.

   If the hung gateway cannot even answer `/positions`, confirm step 2 in the terminal and add `-ConfirmFlatInTerminal`. The script asks you to type `FLAT`. That override applies only when the gateway is silent; it never overrides a gateway that reports exposure.

4. **Rollback (if needed).**

   ```powershell
   .\deploy\mt5_gateway\deploy_main_gateway.ps1 -TargetSha <previous_commit from deploy_main_gateway_verify.json>
   ```

## What Claude verifies right after the restart (read-only)

| # | Check | Evidence source | Pass condition |
|---|---|---|---|
| 1 | Fresh heartbeat | `gateway.quantforg.com/health` | `last_heartbeat` within 60 s, `mt5.connected=true` |
| 2 | Deployed SHA | `docs\production\reports\oat_v71\deploy_main_gateway_verify.json` (owner shares it) and the script log | `commit = 9b52ce67…`, `owner_limits = 9.0 25.0 1.50 0.45` |
| 3 | MT5 identity | Railway log `path=/account` | login `12439799`, server `Weltrade-Real`, `trade_allowed` as MT5 reports it |
| 4 | History | Railway log `path=/history/deals status_code=200` | 200 in under 15 s; circuit closed |
| 5 | UTC offset | backend learns it from `/quotes` | +2 h (Weltrade winter) |
| 6 | Daily loss | engine/ITE logs | daily context trusted; no `mt5_server_clock_unknown`; values match MT5 deals for the UTC day |
| 7 | Risk enforcement | ITE cycle and engine logs | entries outside 9/25/1.5/0.45/07–17 rejected with `OWNER_*`; gateway guard rejects `GUARD_MAX_RISK` above 9% |
| 8 | History/Portfolio pages | signed-in Production check | `/history` and `/portfolio` return 200 |

No LIVE order is sent for any check. LIVE settings and positions are not changed.
