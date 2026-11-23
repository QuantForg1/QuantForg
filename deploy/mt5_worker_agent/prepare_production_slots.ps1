# One-time: create the isolated portable MT5 terminal(s) for the PRODUCTION
# worker slots (QF_MT5_LOCAL_SLOTS, default demo-a) under QF_MT5_SLOT_ROOT.
#
# - Reads local.production.env (never the Staging local.env).
# - COPIES the installed MetaTrader 5 folder; it does not start, stop or modify
#   the LIVE terminal. Bases/Config/Logs are not copied, so the slot starts
#   with no account data.
# - Refuses if free disk is too low. Never uses --force: an existing slot is
#   reused, never wiped.
#
# Usage (repo root):  .\deploy\mt5_worker_agent\prepare_production_slots.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$envFile = Join-Path $PSScriptRoot "local.production.env"
if (-not (Test-Path $envFile)) {
  Write-Host "ERROR: local.production.env not found."
  exit 1
}
Get-Content $envFile | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $pair = $_.Split('=', 2)
  if ($pair.Length -eq 2) {
    Set-Item -Path ("Env:" + $pair[0].Trim()) -Value ($pair[1].Trim().Trim('"').Trim("'"))
  }
}
if (($env:QF_ALLOW_WORKER_ON_LIVE_TERMINAL | ForEach-Object { "$_".ToLower() }) -eq "true") {
  Write-Host "ERROR: QF_ALLOW_WORKER_ON_LIVE_TERMINAL must remain false."
  exit 1
}

$free = (Get-PSDrive C).Free
Write-Host ("Disk free on C: {0:N2} GB" -f ($free / 1GB))
Write-Host "Slot root: $env:QF_MT5_SLOT_ROOT   Slots: $env:QF_MT5_LOCAL_SLOTS"

poetry run python -m services.mt5_worker_agent.main prepare-slots
poetry run python -m services.mt5_worker_agent.main status
