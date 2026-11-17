# Windows MT5 gateway: exact recovery to `a150730e` (owner runbook)

Supersedes `GATEWAY_RECOVERY_2026-11-16.md` (that file had a stale target and a stale heartbeat claim).

## Target

| | Value |
|---|---|
| Gateway SHA | `a150730e9ec59cf8189a4beb92639178fa0cbe5e` |
| Why this SHA | Verified 17 Nov: loading `services.mt5_gateway.main` imports 169 `app/core/services` modules. None of them, and nothing under `services/mt5_gateway` or `deploy/mt5_gateway`, changed between `a150730e` and Production `main`. Everything merged since then is Railway-side only. |
| Script | `deploy/mt5_gateway/deploy_main_gateway.ps1` at that SHA. It requires `-TargetSha`, refuses a dirty tree, checks `/positions` and `/orders` before checkout and before restart, checks out detached, restarts via `supervise_gateway.ps1 -Once`, verifies `/health`, `/account`, `/quotes`, `/candles`, and writes `deploy_main_gateway_verify.json` with `previous_commit`. |
| Running checkout | The gateway's token comes from `C:\QuantForg-Workspace\QuantForg-wt-POLICY\.env` (gateway `/health` `token_fingerprint.source`), so that worktree is most likely `$Root`. Confirm with step 1. |

## Preconditions (Claude verifies these read-only before you start)

1. **The platform terminal is on your account.** You restore Weltrade-Real **12439799** via Broker → Connect/Restore (owner action A13). Claude then confirms from Railway logs that gateway `/account` reports `login 12439799, server Weltrade-Real`.
2. **The heartbeat is fresh.** `gateway.quantforg.com/health` (checked uncached) shows `mt5.last_heartbeat_at` within 60 s, `connected=true`.
3. **Live Trading Control is PAUSED**, and Claude does not change it.
4. **The account is flat.** The MT5 Trade tab shows no positions and no pending orders.

## Procedure (PowerShell as Administrator on the Windows PC)

```powershell
# 1. Find the running checkout
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'services\.mt5_gateway\.main' } |
  Select-Object ProcessId, CommandLine
$Root = "C:\QuantForg-Workspace\QuantForg-wt-POLICY"   # adjust to step 1 output
cd $Root
git status --porcelain        # must print nothing

# 2. Run the reviewed script straight from git
git fetch origin
$Sha = "a150730e9ec59cf8189a4beb92639178fa0cbe5e"
git show "${Sha}:deploy/mt5_gateway/deploy_main_gateway.ps1" |
  Set-Content -Encoding ascii "$env:TEMP\qf_deploy_gateway.ps1"
& "$env:TEMP\qf_deploy_gateway.ps1" -TargetSha $Sha
```

If the gateway cannot answer `/positions`, re-run with `-ConfirmFlatInTerminal`. It asks you to type `FLAT`, and only after you have checked the MT5 Trade tab.

**Rollback:**

```powershell
& "$env:TEMP\qf_deploy_gateway.ps1" -TargetSha <previous_commit from deploy_main_gateway_verify.json>
```

## Post-restart verification (Claude, read-only, no orders)

| # | Check | Pass |
|---|---|---|
| 1 | Uncached `/health` | heartbeat ≤ 60 s, `connected=true` |
| 2 | `deploy_main_gateway_verify.json` | `commit=a150730e…`, `owner_limits=9.0 25.0 1.50 0.45` |
| 3 | Railway log `GET /account` | login 12439799, Weltrade-Real |
| 4 | Railway `slow_request` / `gateway_http_response` for `/history/deals` | 200 in < 15 s; circuit closed |
| 5 | UTC offset learned from `/quotes` | +2 h |
| 6 | Daily-loss context | trusted; matches MT5 deals for the UTC day |
| 7 | Risk gates in ITE logs | entries outside 9/25/1.5/0.45/07–17 rejected `OWNER_*` |
| 8 | History / Portfolio pages (signed in) | 200 with real deals |

LIVE stays PAUSED throughout. Turning it back on needs your separate, explicit authorization.
