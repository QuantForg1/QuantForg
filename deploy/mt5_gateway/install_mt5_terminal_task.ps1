# Register QuantForg MT5 terminal auto-start. Idempotent (same task name).
# Does not store broker passwords. Does not enable Windows auto-logon.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_mt5_terminal_task.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_mt5_terminal_task.ps1 -Uninstall

param(
  [switch]$Uninstall,
  [switch]$SkipStart,
  [string]$TaskName = "QuantForgMT5Terminal"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
  $RepoRoot = (Get-Location).Path
}

$Starter = Join-Path $RepoRoot "deploy\mt5_gateway\start_mt5_terminal.ps1"
if (-not (Test-Path $Starter)) {
  throw "Missing $Starter"
}

if ($Uninstall) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Removed scheduled task $TaskName (if it existed)."
  exit 0
}

$ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Starter`""
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

Write-Host "Scheduled task '$TaskName' registered (AtStartup + AtLogOn, IgnoreNew)."
Write-Host "This task only starts terminal64.exe if it is not already running."

if (-not $SkipStart) {
  Start-ScheduledTask -TaskName $TaskName
  Start-Sleep -Seconds 5
  $procs = @(Get-Process -Name "terminal64","terminal" -ErrorAction SilentlyContinue)
  if ($procs.Count -gt 0) {
    Write-Host ("MT5 process detected pid={0}" -f $procs[0].Id)
  } else {
    Write-Host "WARN: terminal64.exe not detected yet. Log into the VPS desktop and open MT5 once."
  }
}
