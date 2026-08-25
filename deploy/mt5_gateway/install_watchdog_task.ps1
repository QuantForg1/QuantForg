# Register QuantForg VPS watchdog. Idempotent. One-shot per trigger (repeat every 2 min).
# Does not store tokens. Does not use S4U/session-0.
# Interactive + auto-logon is required for MT5; Cloudflared is a LocalSystem service.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_watchdog_task.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_watchdog_task.ps1 -Uninstall

param(
  [switch]$Uninstall,
  [switch]$SkipStart,
  [string]$TaskName = "QuantForgVpsWatchdog"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
  $RepoRoot = (Get-Location).Path
}

$Watch = Join-Path $RepoRoot "deploy\mt5_gateway\watchdog_vps.ps1"
if (-not (Test-Path $Watch)) {
  throw "Missing $Watch"
}

if ($Uninstall) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Removed scheduled task $TaskName (if it existed)."
  exit 0
}

$ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
# One pass per firing. Do NOT append supervise -Once.
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Watch`""
$action = New-ScheduledTaskAction -Execute $ps -Argument $arg -WorkingDirectory $RepoRoot
$once = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$once.Repetition.Interval = "PT2M"
$once.Repetition.Duration = "P9999D"
$triggers = @(
  (New-ScheduledTaskTrigger -AtStartup),
  (New-ScheduledTaskTrigger -AtLogOn),
  $once
)
$settings = New-ScheduledTaskSettingsSet `
  -MultipleInstances IgnoreNew `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
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

Write-Host "Scheduled task '$TaskName' registered (AtStartup + AtLogOn + 2m repeat, IgnoreNew, Highest)."
Write-Host "Interactive is NOT sufficient for unattended reboot; enable auto-logon (operator-owned)."
Write-Host "This script does not store passwords or tunnel tokens."

if (-not $SkipStart) {
  Start-ScheduledTask -TaskName $TaskName
}

Write-Host "Remove: powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_watchdog_task.ps1 -Uninstall"
