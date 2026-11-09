# QuantForg Windows MT5 worker health check (no secrets printed).
# Usage: .\deploy\mt5_worker_agent\health_check.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
  $Root = (Get-Location).Path
}
Set-Location $Root

$EnvFile = Join-Path $PSScriptRoot "local.env"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    if ($_ -match '^([^=]+)=(.*)$') {
      Set-Item -Path "Env:$($Matches[1].Trim())" -Value $Matches[2].Trim()
    }
  }
}

Write-Host "=== QuantForg MT5 worker health ==="
Write-Host "host=$env:COMPUTERNAME root=$Root"
Write-Host "slot_root=$env:QF_MT5_SLOT_ROOT"
Write-Host "api=$env:QUANTFORG_API_BASE_URL"
Write-Host "token_configured=$([bool]($env:WORKER_SERVICE_TOKEN -and $env:WORKER_SERVICE_TOKEN.Length -ge 16))"
Write-Host "live_terminal_override=$env:QF_ALLOW_WORKER_ON_LIVE_TERMINAL"
Write-Host "demo_exness_login_set=$([bool]$env:QF_DEMO_EXNESS_LOGIN)"
Write-Host "demo_hfm_login_set=$([bool]$env:QF_DEMO_HFM_LOGIN)"
Write-Host "generic_demo_login_set=$([bool]$env:QF_DEMO_LOGIN)"

$liveExe = if ($env:QF_LIVE_MT5_TERMINAL_PATH) { $env:QF_LIVE_MT5_TERMINAL_PATH } else { "C:\Program Files\MetaTrader 5\terminal64.exe" }
Write-Host "live_mt5_present=$(Test-Path $liveExe)"

poetry run python -m services.mt5_worker_agent.main status
if ($env:WORKER_SERVICE_TOKEN -and $env:QUANTFORG_API_BASE_URL) {
  poetry run python -m services.mt5_worker_agent.main railway-ping
} else {
  Write-Host "railway-ping skipped (token/url missing)"
}
