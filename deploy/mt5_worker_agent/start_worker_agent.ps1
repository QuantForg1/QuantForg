# QuantForg MT5 Worker Agent launcher (Windows host).
# Does NOT place trades. Does NOT enable LIVE multi-user submit.
# Requires owner-approved Windows host + WORKER_SERVICE_TOKEN.
#
# Usage (elevated / interactive session with MT5 available):
#   .\start_worker_agent.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
  $Root = (Get-Location).Path
}

Write-Host "QuantForg MT5 Worker Agent"
Write-Host "Repo root: $Root"
Write-Host "This script starts the agent process. It does not provision cloud VMs."

if (-not $env:WORKER_SERVICE_TOKEN -or $env:WORKER_SERVICE_TOKEN.Trim().Length -lt 16) {
  Write-Host "ERROR: WORKER_SERVICE_TOKEN missing or too short (need >= 16 chars)."
  Write-Host "Do not commit the token. Obtain it from the QuantForg control plane."
  exit 1
}

$tokenLen = $env:WORKER_SERVICE_TOKEN.Trim().Length
Write-Host "WORKER_SERVICE_TOKEN configured (length=$tokenLen; value not shown)."

if (-not $env:QUANTFORG_API_BASE_URL) {
  Write-Host "WARN: QUANTFORG_API_BASE_URL unset — agent cannot phone home yet."
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  Write-Host "ERROR: python not found on PATH."
  exit 1
}

Set-Location $Root
Write-Host "Launching: python -m services.mt5_worker_agent.main"
python -m services.mt5_worker_agent.main
