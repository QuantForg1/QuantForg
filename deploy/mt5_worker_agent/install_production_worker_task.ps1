# Install (or remove) a Windows Scheduled Task that keeps the PRODUCTION MT5
# worker supervisor running in the background: starts at logon, hidden, and is
# restarted automatically if it stops. No terminal window has to stay open.
#
# Usage (PowerShell, from the repo root):
#   .\deploy\mt5_worker_agent\install_production_worker_task.ps1            # install + start
#   .\deploy\mt5_worker_agent\install_production_worker_task.ps1 -Remove    # uninstall
#   .\deploy\mt5_worker_agent\install_production_worker_task.ps1 -Status    # show state + log tail
#
# Safety: runs only start_production_supervisor.ps1 (which refuses Staging,
# refuses QF_ALLOW_WORKER_ON_LIVE_TERMINAL=true, and never touches the LIVE
# terminal). It stores no secrets: the token stays in local.production.env.
# Needs a signed-in Windows session (MetaTrader 5 is a desktop program).

param(
  [switch]$Remove,
  [switch]$Status,
  [string]$TaskName = "QuantForg-Production-MT5-Worker"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Starter = Join-Path $PSScriptRoot "start_production_supervisor.ps1"
$EnvFile = Join-Path $PSScriptRoot "local.production.env"
$LogDir = Join-Path $env:LOCALAPPDATA "QuantForg\worker"
$LogFile = Join-Path $LogDir "supervisor.log"

if ($Status) {
  $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if (-not $t) { Write-Host "Task '$TaskName' is not installed."; exit 1 }
  $info = Get-ScheduledTaskInfo -TaskName $TaskName
  Write-Host "State: $($t.State)   LastRun: $($info.LastRunTime)   LastResult: $($info.LastTaskResult)"
  if (Test-Path $LogFile) { Write-Host "--- last log lines ---"; Get-Content $LogFile -Tail 15 }
  exit 0
}

if ($Remove) {
  if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed task '$TaskName'."
  } else {
    Write-Host "Task '$TaskName' was not installed."
  }
  exit 0
}

if (-not (Test-Path $Starter)) { throw "Missing $Starter" }
if (-not (Test-Path $EnvFile)) {
  throw "local.production.env not found. Create it first (copy local.production.env.example)."
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Small launcher written next to the log (keeps the task command short and
# avoids quoting problems). Rotates the log at ~2 MB.
$RunScript = Join-Path $LogDir "run_worker.ps1"
$Launcher = @"
Set-Location '$Root'
if ((Test-Path '$LogFile') -and ((Get-Item '$LogFile').Length -gt 2MB)) { Move-Item -Force '$LogFile' '${LogFile}.old' }
& '$Starter' *>> '$LogFile'
"@
Set-Content -Path $RunScript -Value $Launcher -Encoding UTF8

# Stop any running worker (old code stays in memory otherwise, and the task
# uses -MultipleInstances IgnoreNew so a new start would be silently ignored).
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {
    $_.ProcessId -ne $PID -and $_.CommandLine -and
    $_.CommandLine -match 'services\.mt5_worker_agent|start_production_supervisor|run_worker\.ps1'
  } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
# Only the worker's own slot terminals (never the LIVE terminal).
Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.ExecutablePath -and $_.ExecutablePath -like '*mt5_worker_slots_production*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$RunScript`"" `
  -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -MultipleInstances IgnoreNew `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
  -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Installed and started '$TaskName'."
Write-Host "Log: $LogFile"
Write-Host "Check any time:  .\deploy\mt5_worker_agent\install_production_worker_task.ps1 -Status"
