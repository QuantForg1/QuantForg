# Reclaim a hung MT5 Gateway on 127.0.0.1:8765 and start a supervised instance.
# Run from an ELEVATED PowerShell (right-click -> Run as administrator) when
# /health/live times out but netstat still shows LISTENING.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\reclaim_gateway.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

Write-Host "Reclaiming listeners on :8765 ..."
$pids = @(
  Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
)
if ($pids.Count -eq 0) {
  Write-Host "No LISTEN on :8765"
} else {
  foreach ($procId in $pids) {
    Write-Host "taskkill /F /PID $procId"
    & taskkill /F /PID $procId
  }
  Start-Sleep -Seconds 3
}

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "supervise_gateway.ps1") -Once
if ($LASTEXITCODE -ne 0) { throw "supervise_gateway.ps1 -Once failed" }

Write-Host "Verify:"
netstat -ano | findstr ":8765"
Invoke-RestMethod "http://127.0.0.1:8765/health/live" -TimeoutSec 5 | ConvertTo-Json -Compress
Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 8 | Select-Object status, gateway_version, bridge_available | ConvertTo-Json -Compress
