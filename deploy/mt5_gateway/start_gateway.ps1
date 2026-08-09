# QuantForg MT5 Gateway - start via Poetry / Python 3.13 project venv.
# Do NOT use bare "py -m" or global Python 3.14 (missing project deps / uvicorn).
#
# From repo root:
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\start_gateway.ps1
#
# If http://127.0.0.1:8765/health is already healthy, this script exits without
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

function Test-LocalGatewayHealthy {
  try {
    $h = Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 8
    return (
      $h.status -eq "ok" -and
      $h.token_configured -eq $true -and
      $h.bridge_available -eq $true -and
      $h.mt5.connected -eq $true
    )
  } catch {
    return $false
  }
}

Write-Host "RepoRoot=$RepoRoot"

$listen = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($listen) {
  if (Test-LocalGatewayHealthy) {
    Write-Host "Gateway already healthy on :8765 - not starting a second process."
    $h = Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 8
    Write-Host ("status={0} mt5.connected={1} trade_allowed={2} autotrading={3}" -f `
      $h.status, $h.mt5.connected, $h.mt5.trade_allowed, $h.mt5.mt5_autotrading_enabled)
    exit 0
  }
  Write-Host "Port 8765 is occupied but health check failed. Stop the old process before restarting."
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
& $Python -m services.mt5_gateway.main
