# Install a Windows Scheduled Task for the local MT5 worker supervisor.
# Does not enable LIVE multi-account submit. Run elevated if required.
# Usage: .\deploy\mt5_worker_agent\install_scheduled_task.ps1

param(
  [string]$TaskName = "QuantForg-MT5-Worker-Supervisor",
  [switch]$Remove
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
$Supervisor = Join-Path $ScriptDir "start_local_supervisor.ps1"

if ($Remove) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Removed task $TaskName (if present)"
  exit 0
}

if (-not (Test-Path $Supervisor)) {
  throw "Missing $Supervisor"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Supervisor`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Registered Scheduled Task: $TaskName"
Write-Host "Starts at logon. LIVE Program Files terminal is never used by workers."
