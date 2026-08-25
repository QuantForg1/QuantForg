# Register QuantForg MT5 Gateway as a persistent Windows Scheduled Task.
# Idempotent: the same task name is replaced, never duplicated.
#
# Triggers:
#   AtStartup  - unattended VPS reboot (requires auto-logon OR "run whether logged on")
#   AtLogOn    - recovery when the trading user session appears
#
# This script does NOT claim the task is already installed on any host.
# Run it ON the Windows VPS (elevated PowerShell if Access Denied).
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_gateway_task.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_gateway_task.ps1 -Uninstall

param(
  [switch]$Uninstall,
  [switch]$SkipStart,
  [string]$TaskName = "QuantForgMT5Gateway"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
  $RepoRoot = (Get-Location).Path
}

$Supervise = Join-Path $RepoRoot "deploy\mt5_gateway\supervise_gateway.ps1"
if (-not (Test-Path $Supervise)) {
  throw "Missing $Supervise"
}

if ($Uninstall) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Removed scheduled task $TaskName (if it existed)."
  exit 0
}

$ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Supervise`""
$action = New-ScheduledTaskAction -Execute $ps -Argument $arg -WorkingDirectory $RepoRoot
$triggers = @(
  (New-ScheduledTaskTrigger -AtStartup),
  (New-ScheduledTaskTrigger -AtLogOn)
)
$settings = New-ScheduledTaskSettingsSet `
  -MultipleInstances IgnoreNew `
  -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 1) `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -DontStopOnIdleEnd
$principal = New-ScheduledTaskPrincipal `
  -UserId $env:USERNAME `
  -LogonType Interactive `
  -RunLevel Highest

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $triggers `
  -Settings $settings `
  -Principal $principal `
  -Force | Out-Null

Write-Host "Scheduled task '$TaskName' registered (AtStartup + AtLogOn, IgnoreNew, no time limit)."
Write-Host "WorkingDirectory=$RepoRoot"
Write-Host "NOTE: Interactive logon type needs the trading user session (auto-logon on a VPS)."
Write-Host "This script does not enable Windows auto-logon and does not store passwords."

if (-not $SkipStart) {
  Start-ScheduledTask -TaskName $TaskName
  Start-Sleep -Seconds 8
  try {
    $live = Invoke-RestMethod "http://127.0.0.1:8765/health/live" -TimeoutSec 5
    Write-Host ("/health/live status={0} version={1}" -f $live.status, $live.gateway_version)
  } catch {
    Write-Host "WARN: /health/live not ready yet. Check docs\production\reports\gateway_supervisor\supervisor.log"
  }
}

Write-Host ""
Write-Host "Manual controls:"
Write-Host "  Start:  Start-ScheduledTask -TaskName $TaskName"
Write-Host "  Stop:   create file docs\production\reports\gateway_supervisor\STOP"
Write-Host "  Remove: powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_gateway_task.ps1 -Uninstall"
