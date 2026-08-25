# Operator-controlled recovery helpers for the Windows MT5 Gateway host.
# NEVER calls order_send, NEVER places BUY/SELL, NEVER modifies SL/TP.
# NEVER reboots the machine.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\recover_production_vps.ps1 -Action Status
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\recover_production_vps.ps1 -Action RestartGateway
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\recover_production_vps.ps1 -Action RestartSupervisor
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\recover_production_vps.ps1 -Action RestartMt5
#
# RestartMt5 is documented as optional: it only restarts terminal64.exe.
# It does not reconnect the broker with a password and does not trade.

param(
  [ValidateSet("Status","RestartGateway","RestartSupervisor","RestartMt5","ReclaimPort")]
  [string]$Action = "Status",
  [string]$RepoRoot = "",
  [string]$GatewayTaskName = "QuantForgMT5Gateway",
  [string]$TerminalTaskName = "QuantForgMT5Terminal"
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
Set-Location $RepoRoot
$ReportDir = Join-Path $RepoRoot "docs\production\reports\gateway_supervisor"
$StopFile = Join-Path $ReportDir "STOP"

function Write-Rec([string]$msg) {
  Write-Host ("[{0}] {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $msg)
}

function Get-ListenPids {
  $pids = @()
  $lines = & netstat -ano -p tcp 2>$null
  foreach ($line in $lines) {
    if ($line -match ":8765\s+\S+\s+LISTENING\s+(\d+)\s*$") {
      $pids += [int]$Matches[1]
    }
  }
  return @($pids | Select-Object -Unique)
}

Write-Rec ("recover action={0} repo={1}" -f $Action, $RepoRoot)

switch ($Action) {
  "Status" {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "deploy\mt5_gateway\verify_production_vps.ps1") -RepoRoot $RepoRoot
    exit $LASTEXITCODE
  }
  "RestartGateway" {
    Write-Rec "gateway restart via STOP then scheduled task"
    New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
    Set-Content -Path $StopFile -Value "stop" -Encoding ASCII
    Start-Sleep -Seconds 4
    if (Test-Path $StopFile) { Remove-Item $StopFile -Force }
    foreach ($procId in (Get-ListenPids)) {
      Write-Rec ("stopping listener pid={0}" -f $procId)
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-ScheduledTask -TaskName $GatewayTaskName
    Start-Sleep -Seconds 8
    Invoke-RestMethod "http://127.0.0.1:8765/health/live" -TimeoutSec 8 | ConvertTo-Json -Compress
  }
  "RestartSupervisor" {
    Write-Rec "supervisor restart via scheduled task (IgnoreNew prevents duplicates)"
    Start-ScheduledTask -TaskName $GatewayTaskName
    Start-Sleep -Seconds 5
    Write-Rec "task start requested"
  }
  "RestartMt5" {
    Write-Rec "OPTIONAL mt5 process restart - no order_send"
    $procs = @(Get-Process -Name "terminal64","terminal" -ErrorAction SilentlyContinue)
    foreach ($p in $procs) {
      Write-Rec ("stopping mt5 pid={0}" -f $p.Id)
      Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 3
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "deploy\mt5_gateway\start_mt5_terminal.ps1")
    Write-Rec "MT5 start requested. Gateway delayed auto-attach should recover without a forced trade."
  }
  "ReclaimPort" {
    Write-Rec "reclaim hung :8765 then supervise -Once"
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "deploy\mt5_gateway\reclaim_gateway.ps1")
  }
}

Write-Rec "recovery command finished (no live order was sent by this script)"
exit 0
