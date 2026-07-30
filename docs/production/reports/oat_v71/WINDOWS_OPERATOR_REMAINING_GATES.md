# Windows operator — remaining gates for v7.1 acceptance

Branch: `cursor/v7-1-acceptance-evidence`  
Repo-side status: reconnect fix deployed (`gateway_version=1.1.1`).  
**PAT/OAT remain NOT ACCEPTED until the steps below are done and verified.**

Cloud agents cannot perform these steps (no Windows shell, no `MT5_GATEWAY_TOKEN` in cloud env).

---

## 1. Restore MT5 on the live gateway

1. Confirm MetaTrader 5 is running and **logged into** Weltrade-Real (or the production account).
2. From the QuantForg repo on the Windows host, load the gateway token from `.env` (never commit it):

```powershell
cd "C:\Users\P7 PROVIDER\QuantForg"
$token = (Get-Content .env | Where-Object { $_ -match '^\s*MT5_GATEWAY_TOKEN\s*=' } | Select-Object -Last 1)
$token = ($token -split '=',2)[1].Trim().Trim('"').Trim("'")
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8765/session/attach" `
  -Headers @{ Authorization = "Bearer $token"; Accept = "application/json" } `
  -ContentType "application/json" -Body "{}"
Invoke-RestMethod "http://127.0.0.1:8765/health" | ConvertTo-Json -Depth 6
```

3. Public check must show `gateway_version=1.1.1` and `mt5.connected=true`:

```powershell
Invoke-RestMethod "https://gateway.quantforg.com/health" | ConvertTo-Json -Depth 6
```

If attach fails, log into the MT5 UI first, then retry. `auto_attach_enabled` is true but only works when the terminal already has an account session.

---

## 2. Complete post-fix soak (≥24h)

With MT5 attached and gateway 1.1.1 running:

```powershell
cd "C:\Users\P7 PROVIDER\QuantForg"
# If soak is not already running:
powershell -NoProfile -ExecutionPolicy Bypass -File ".\docs\production\reports\oat_v71\soak_24h.ps1"
```

Do not declare complete until `soak_24h_metrics.jsonl` spans **≥24 hours** of samples **after** the 1.1.1 deploy, with MT5 connected for the majority of samples (brief self-healed blips only).

---

## 3. Synchronize soak evidence to git

```powershell
cd "C:\Users\P7 PROVIDER\QuantForg"
git checkout cursor/v7-1-acceptance-evidence
git pull origin cursor/v7-1-acceptance-evidence
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\sync_windows_soak_evidence.ps1"
# Also add deploy/soak start markers and Step 4 files if present:
git add docs/production/reports/oat_v71/post_fix_deploy.json `
        docs/production/reports/oat_v71/post_fix_soak_start.json `
        docs/production/reports/oat_v71/step4_remember_me_*.json `
        2>$null
git status
git push origin cursor/v7-1-acceptance-evidence
```

---

## 4. Remember Me (OAT Step 4)

Follow `docs/production/reports/oat_v71/REMEMBER_ME_OPERATOR_CHECKLIST.md`.

Write evidence files:

- `docs/production/reports/oat_v71/step4_remember_me_refresh.json`
- `docs/production/reports/oat_v71/step4_remember_me_browser_reopen.json`
- `docs/production/reports/oat_v71/step4_remember_me_pc_restart.json`

Commit and push them on `cursor/v7-1-acceptance-evidence`.

---

## 5. After evidence is in git

Ask the release engineer / cloud agent to re-run PAT and OAT.  
**Release to `main` only if both are ACCEPTED with verified evidence.**
