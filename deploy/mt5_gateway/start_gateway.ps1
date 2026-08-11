# QuantForg MT5 Gateway - interactive / foreground start via Poetry venv.
# Do NOT use bare "py -m" or global Python 3.14 (missing project deps / uvicorn).
#
# From repo root:
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\start_gateway.ps1
#
# Production (survives terminal close + auto-restart):
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\supervise_gateway.ps1 -Once
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_gateway_task.ps1
#
# If http://127.0.0.1:8765/health/live is already ok, this script exits without
# starting a second process.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
  $RepoRoot = (Get-Location).Path
}
Set-Location $RepoRoot

function Get-ProjectPython {
  $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) {
    return $venvPy
  }
  $info = & py -3.13 -m poetry env info -p 2>$null
  if ($LASTEXITCODE -eq 0 -and $info) {
    $candidate = Join-Path $info.Trim() "Scripts\python.exe"
    if (Test-Path $candidate) { return $candidate }
  }
  throw "Project venv not found. Run: py -3.13 -m poetry install"
}

function Test-LocalGatewayLive {
  try {
    $h = Invoke-RestMethod "http://127.0.0.1:8765/health/live" -TimeoutSec 3
    return ($h.status -eq "ok" -and $h.service -eq "mt5-gateway")
  } catch {
    return $false
  }
}

Write-Host "RepoRoot=$RepoRoot"
Write-Host "TIP: For production use deploy\mt5_gateway\supervise_gateway.ps1 (survives terminal close)."

$listen = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($listen) {
  if (Test-LocalGatewayLive) {
    Write-Host "Gateway already live on :8765 - not starting a second process."
    try {
      $h = Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 5
      Write-Host ("status={0} mt5.connected={1} trade_allowed={2} autotrading={3}" -f `
        $h.status, $h.mt5.connected, $h.mt5.trade_allowed, $h.mt5.mt5_autotrading_enabled)
    } catch {
      Write-Host "Gateway process is live; /health degraded or slow (MT5 busy) --- not restarting."
    }
    exit 0
  }
  Write-Host "Port 8765 is occupied but /health/live failed (hung/stale process)."
  Write-Host "Reclaim with: powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\supervise_gateway.ps1 -Once"
  $listen | ForEach-Object {
    $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
    Write-Host ("LISTEN pid={0} name={1}" -f $_.OwningProcess, $p.ProcessName)
  }
  exit 1
}

$Python = Get-ProjectPython
Write-Host "Using Python=$Python"
# Use single-quoted -c so PowerShell does not parse Python syntax.
& $Python -c 'import sys,uvicorn; print(sys.version.split()[0]); print(uvicorn.__version__)'
if ($LASTEXITCODE -ne 0) {
  throw "uvicorn missing in project env. Run: py -3.13 -m poetry install"
}

Write-Host "Starting gateway (foreground). Ctrl+C to stop."
Write-Host "NOTE: Closing this window stops the gateway. Prefer supervise_gateway.ps1 for production."
& $Python -m services.mt5_gateway.main

