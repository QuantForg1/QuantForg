# Start Production-targeted multi-slot supervisor on a Windows host.
# Does NOT load Staging local.env.
# Does NOT kill or reconfigure the LIVE Program Files terminal.
# Does NOT enable LIVE multi-user order submit.
#
# Prerequisites:
#   1) Copy local.production.env.example → local.production.env
#   2) Set Production WORKER_SERVICE_TOKEN + DEMO credentials
#   3) Keep deploy/mt5_worker_agent/local.env aimed at Staging (untouched)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$envFile = Join-Path $PSScriptRoot "local.production.env"
if (-not (Test-Path $envFile)) {
  Write-Host "ERROR: local.production.env not found."
  Write-Host "Copy local.production.env.example first. Do not reuse Staging local.env."
  exit 1
}

Get-Content $envFile | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $pair = $_.Split('=', 2)
  if ($pair.Length -eq 2) {
    $name = $pair[0].Trim()
    $val = $pair[1].Trim().Trim('"').Trim("'")
    Set-Item -Path "Env:$name" -Value $val
  }
}
Write-Host "Loaded local.production.env (values not printed)."

$api = ($env:QUANTFORG_API_BASE_URL | ForEach-Object { $_ })
if (-not $api -or $api -notmatch 'quantforg-production\.up\.railway\.app') {
  Write-Host "ERROR: QUANTFORG_API_BASE_URL must target Production Railway."
  Write-Host "Refusing to start to protect Staging/Production isolation."
  exit 1
}

if ($api -match 'staging') {
  Write-Host "ERROR: Staging URL detected in production supervisor. Aborting."
  exit 1
}

if (-not $env:WORKER_SERVICE_TOKEN -or $env:WORKER_SERVICE_TOKEN.Trim().Length -lt 16) {
  Write-Host "ERROR: WORKER_SERVICE_TOKEN missing or too short."
  exit 1
}

if (($env:QF_ALLOW_WORKER_ON_LIVE_TERMINAL | ForEach-Object { $_.ToLower() }) -eq "true") {
  Write-Host "ERROR: QF_ALLOW_WORKER_ON_LIVE_TERMINAL must remain false."
  exit 1
}

Write-Host "QuantForg PRODUCTION MT5 worker supervisor"
Write-Host "API base configured for Production (URL not re-printed with secrets)."
Write-Host "LIVE terminal override = $env:QF_ALLOW_WORKER_ON_LIVE_TERMINAL (must be false)"
# Unbuffered so the background task log shows every line immediately.
$env:PYTHONUNBUFFERED = "1"
# Merge stderr into stdout at the cmd level. Python logs to stderr; under
# $ErrorActionPreference="Stop" a redirected stderr line becomes a terminating
# NativeCommandError in Windows PowerShell, which killed the supervisor right
# after its first log line when run from the background task.
$ErrorActionPreference = "Continue"
cmd /c "poetry run python -m services.mt5_worker_agent.main supervise 2>&1"
