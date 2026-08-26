# One-command unattended-reboot readiness workflow. Idempotent.
# NEVER accepts a password. NEVER prints secrets. NEVER reboots. NEVER places trades.
# NEVER creates a local user. NEVER uses S4U/session-0.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\finalize_unattended_reboot.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\finalize_unattended_reboot.ps1 -SkipUi

param(
  [switch]$SkipUi
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
  $RepoRoot = (Get-Location).Path
}
Set-Location $RepoRoot

$ProcessHelpers = Join-Path $PSScriptRoot "_gateway_process.ps1"
$HostHelpers = Join-Path $PSScriptRoot "_host_recovery.ps1"
if (-not (Test-Path $ProcessHelpers) -or -not (Test-Path $HostHelpers)) {
  Write-Host "ERROR: missing helper scripts"
  exit 2
}
. $ProcessHelpers
. $HostHelpers

function Test-IsAdministrator {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object Security.Principal.WindowsPrincipal($id)
  return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-Host "QuantForg finalize unattended reboot (does not reboot, does not send orders)"
Write-Host ("hostname={0} user={1}" -f $env:COMPUTERNAME, $env:USERNAME)
if (-not (Test-IsAdministrator)) {
  Write-Host "ERROR: run this script from an elevated PowerShell (Administrator)."
  exit 2
}

$admin = Get-LocalAdministratorState
if (-not $admin.Exists) {
  Write-Host "ERROR: local Administrator account was not found. No user was created."
  exit 2
}
if (-not $admin.Enabled) {
  Write-Host "ERROR: Administrator account is disabled. Not enabling it automatically."
  exit 2
}
Write-Host ("Administrator exists=true enabled=true password_configured={0}" -f $admin.PasswordConfigured)
if (-not $admin.PasswordConfigured) {
  Write-Host "ACTION_REQUIRED: Administrator has no password set. Set it in Windows, not in this script."
}

$principalOk = $true
foreach ($tn in @("QuantForgMT5Gateway", "QuantForgMT5Terminal", "QuantForgVpsWatchdog")) {
  $t = Get-ScheduledTask -TaskName $tn -ErrorAction SilentlyContinue
  if ($null -eq $t) {
    Write-Host ("FAIL task {0} not registered" -f $tn)
    $principalOk = $false
    continue
  }
  $uid = [string]$t.Principal.UserId
  Write-Host ("task {0} user={1} logon={2} runlevel={3} state={4}" -f $tn, $uid, $t.Principal.LogonType, $t.Principal.RunLevel, $t.State)
  if ($t.Principal.LogonType -eq "S4U") {
    Write-Host "ERROR: S4U is not allowed for MT5/Gateway tasks."
    exit 2
  }
}
$wd = Get-ScheduledTask -TaskName "QuantForgVpsWatchdog" -ErrorAction SilentlyContinue
$repeatOk = $false
if ($null -ne $wd) {
  foreach ($tr in @($wd.Triggers)) {
    if ($null -eq $tr.Repetition) { continue }
    $iv = [string]$tr.Repetition.Interval
    if ($iv -match "PT2M" -or $iv -match "^00:02:00") { $repeatOk = $true }
  }
}
Write-Host ("watchdog_repetition_2m={0}" -f $repeatOk)

$cf = Get-CloudflaredService
$cfOk = ($null -ne $cf -and $cf.StartType -eq "Automatic")
Write-Host ("cloudflared_automatic={0} status={1}" -f $cfOk, $(if ($null -ne $cf) { $cf.Status } else { "missing" }))
Write-Host ("cloudflared_scm_restart={0}" -f (Test-CloudflaredScmRestartConfigured))
Write-Host ("cloudflared_command={0}" -f (Get-CloudflaredCommandSanitized))

$mt5Exe = Resolve-Mt5TerminalPath
Write-Host ("mt5_executable_exists={0}" -f (Test-Path -LiteralPath $mt5Exe))
$listen = @(Get-GatewayListenPids)
$liveOk = Test-LocalGatewayLiveOk -TimeoutSec 5
$publicOk = Test-PublicGatewayLive
$mt5Pids = @(Get-Mt5TerminalPids)
Write-Host ("gateway_listener_count={0} local_live={1} public_live={2} mt5_count={3}" -f $listen.Count, $liveOk, $publicOk, $mt5Pids.Count)

$provider = Get-ProviderPowerReadiness
Write-Host ("PROVIDER POWER RECOVERY: {0}" -f $provider.State)

$auto = Get-AutoLogonReadiness
Write-Host ("AUTO_LOGON: {0} SecretStorage={1}" -f $auto.State, $auto.SecretStorage)

if ($auto.State -ne "READY" -and -not $SkipUi) {
  Write-Host ""
  Write-Host "Operator action required: enter the Administrator password only in the Sysinternals Autologon Windows dialog."
  Write-AutologonOperatorInstructions
  $ui = Join-Path $PSScriptRoot "open_autologon_ui.ps1"
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ui -LaunchUi -Wait
  $auto = Get-AutoLogonReadiness
  Write-Host ("AUTO_LOGON after UI: {0}" -f $auto.State)
}

Write-Host ""
$verify = Join-Path $PSScriptRoot "verify_production_vps.ps1"
$reboot = Join-Path $PSScriptRoot "verify_reboot_readiness.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verify -RepoRoot $RepoRoot
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $reboot -RepoRoot $RepoRoot

$auto = Get-AutoLogonReadiness
$provider = Get-ProviderPowerReadiness
$listen = @(Get-GatewayListenPids)
$liveOk = Test-LocalGatewayLiveOk -TimeoutSec 5
$publicOk = Test-PublicGatewayLive
$mt5Pids = @(Get-Mt5TerminalPids)
$hostLocal = ($listen.Count -eq 1 -and $liveOk -and $mt5Pids.Count -ge 1 -and (Test-CloudflaredServiceRunning))
$software = ($repeatOk -and $principalOk -and (Test-Path -LiteralPath $mt5Exe) -and $cfOk)
$rebootReady = ($hostLocal -and $software -and ($auto.State -eq "READY") -and ($provider.State -eq "READY") -and $admin.Exists -and $admin.Enabled)

Write-Host ""
Write-Host ("SOFTWARE RECOVERY READY: {0}" -f $(if ($software) { "YES" } else { "NO" }))
Write-Host ("AUTO_LOGON: {0}" -f $auto.State)
Write-Host ("PROVIDER POWER RECOVERY: {0}" -f $provider.State)
Write-Host ("REBOOT READINESS: {0}" -f $(if ($rebootReady) { "READY" } else { "ACTION_REQUIRED" }))
Write-Host ("PUBLIC TUNNEL HEALTHY: {0}" -f $(if ($publicOk) { "YES" } else { "NO" }))
Write-Host ("LIVE ORDER SENT: NO")
if ($auto.State -ne "READY") {
  Write-Host "Remaining operator action: in Autologon set Username=Administrator Domain=. and enter the password only in that dialog."
}
if ($provider.State -ne "READY") {
  Write-Host "Remaining operator action: attest provider power recovery after confirming the VPS panel."
}
if ($rebootReady) { exit 0 }
exit 0
