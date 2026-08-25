# Reboot-readiness check. NEVER reboots. NEVER places trades.
# NEVER prints DefaultPassword, tokens, or Authorization headers.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\verify_reboot_readiness.ps1

param(
  [string]$RepoRoot = ""
)

$ErrorActionPreference = "Continue"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

$ProcessHelpers = Join-Path $PSScriptRoot "_gateway_process.ps1"
$HostHelpers = Join-Path $PSScriptRoot "_host_recovery.ps1"
if (-not (Test-Path $ProcessHelpers) -or -not (Test-Path $HostHelpers)) {
  Write-Host "REBOOT READINESS: ACTION_REQUIRED"
  Write-Host "missing helper scripts"
  exit 2
}
. $ProcessHelpers
. $HostHelpers

$Fail = 0
$Warn = 0
$Pass = 0
function Add-Check {
  param([string]$Name, [string]$Status, [string]$Detail)
  Write-Host ("[{0}] {1} - {2}" -f $Status, $Name, $Detail)
  if ($Status -eq "FAIL") { $script:Fail++ }
  elseif ($Status -eq "WARN") { $script:Warn++ }
  else { $script:Pass++ }
}

Write-Host "QuantForg reboot readiness (does not reboot, does not send orders)"
Write-Host ("hostname={0}" -f $env:COMPUTERNAME)
Write-Host ("interactive_user={0}" -f $env:USERNAME)

try {
  $boot = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
  if ($boot) {
    Add-Check "windows_last_boot" "PASS" ([datetime]$boot.LastBootUpTime).ToUniversalTime().ToString("o")
  } else {
    Add-Check "windows_last_boot" "WARN" "unreadable"
  }
} catch {
  Add-Check "windows_last_boot" "WARN" "unreadable"
}
Add-Check "provider_power_loss" "WARN" "UNKNOWN unless operator attested; Windows guest cannot read BIOS/hypervisor power-on"

$auto = Get-AutoLogonReadiness
if ($auto.State -eq "READY") {
  Add-Check "auto_logon" "PASS" ("READY user_configured={0} interactive={1}" -f $auto.UserConfigured, $auto.InteractiveUser)
} else {
  Add-Check "auto_logon" "WARN" "ACTION_REQUIRED (software cannot enable Auto-Logon; use open_autologon_ui.ps1 -LaunchUi)"
}

$provider = Get-ProviderPowerReadiness
if ($provider.State -eq "READY") {
  Add-Check "provider_power_recovery" "PASS" "READY (operator attestation; not a guest BIOS probe)"
} else {
  Add-Check "provider_power_recovery" "WARN" "UNKNOWN (confirm in VPS panel, then confirm_provider_power_recovery.ps1 -IConfirmTheProviderIsConfigured)"
}

function Test-NamedTask {
  param([string]$Name, [switch]$RequireRepeat)
  $t = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
  if ($null -eq $t) {
    Add-Check "task:$Name" "FAIL" "not registered"
    return $false
  }
  $ok = $true
  if ($RequireRepeat) {
    $repeat = $false
    foreach ($tr in @($t.Triggers)) {
      if ($null -eq $tr.Repetition) { continue }
      $iv = [string]$tr.Repetition.Interval
      if ($iv -match "PT2M" -or $iv -match "^00:02:00") { $repeat = $true }
    }
    if ($repeat) {
      Add-Check "task:$Name" "PASS" "registered + 2m repetition"
    } else {
      Add-Check "task:$Name" "FAIL" "missing 2-minute repetition"
      $ok = $false
    }
  } else {
    Add-Check "task:$Name" "PASS" ("state={0}" -f $t.State)
  }
  return $ok
}

$gwTask = Test-NamedTask -Name "QuantForgMT5Gateway"
$mt5Task = Test-NamedTask -Name "QuantForgMT5Terminal"
$wdTask = Test-NamedTask -Name "QuantForgVpsWatchdog" -RequireRepeat

$cf = Get-CloudflaredService
if ($null -eq $cf) {
  Add-Check "cloudflared_service" "FAIL" "not installed"
} elseif ($cf.StartType -ne "Automatic") {
  Add-Check "cloudflared_service" "FAIL" ("StartType={0} expected Automatic" -f $cf.StartType)
} else {
  Add-Check "cloudflared_service" "PASS" ("Automatic status={0}" -f $cf.Status)
}
if (Test-CloudflaredScmRestartConfigured) {
  Add-Check "cloudflared_scm_recovery" "PASS" "restart on failure configured"
} else {
  Add-Check "cloudflared_scm_recovery" "WARN" "run harden_cloudflared_service.ps1 elevated"
}
Add-Check "cloudflared_command" "PASS" (Get-CloudflaredCommandSanitized)

$mt5Exe = Resolve-Mt5TerminalPath
if (Test-Path -LiteralPath $mt5Exe) {
  Add-Check "mt5_executable" "PASS" $mt5Exe
} else {
  Add-Check "mt5_executable" "FAIL" "terminal64.exe not found"
}

$supervise = Join-Path $RepoRoot "deploy\mt5_gateway\supervise_gateway.ps1"
$watch = Join-Path $RepoRoot "deploy\mt5_gateway\watchdog_vps.ps1"
if (Test-Path $supervise) { Add-Check "gateway_supervisor_script" "PASS" $supervise } else { Add-Check "gateway_supervisor_script" "FAIL" "missing" }
if (Test-Path $watch) { Add-Check "watchdog_script" "PASS" $watch } else { Add-Check "watchdog_script" "FAIL" "missing" }

$listen = @(Get-GatewayListenPids)
$liveOk = Test-LocalGatewayLiveOk -TimeoutSec 5
$mt5Procs = @(Get-Mt5TerminalPids)
$cfPids = @(Get-CloudflaredPids)
if ($listen.Count -eq 1 -and $liveOk) {
  Add-Check "current_gateway" "PASS" ("listener={0}" -f $listen[0])
} elseif ($listen.Count -gt 1) {
  Add-Check "current_gateway" "FAIL" ("duplicate listeners={0}" -f ($listen -join ","))
} else {
  Add-Check "current_gateway" "WARN" "Gateway not live now (watchdog can recover after boot if auto-logon is READY)"
}
if ($mt5Procs.Count -eq 1) {
  Add-Check "current_mt5" "PASS" ("pid={0}" -f $mt5Procs[0])
} elseif ($mt5Procs.Count -gt 1) {
  Add-Check "current_mt5" "WARN" ("duplicate terminal count={0}" -f $mt5Procs.Count)
} else {
  Add-Check "current_mt5" "WARN" "terminal64 not running now"
}
if ($cfPids.Count -eq 1) {
  Add-Check "current_cloudflared" "PASS" ("pid={0}" -f $cfPids[0])
} elseif ($cfPids.Count -gt 1) {
  Add-Check "current_cloudflared" "WARN" ("duplicate count={0} not killed" -f $cfPids.Count)
} else {
  Add-Check "current_cloudflared" "WARN" "cloudflared.exe not running now"
}

$configReady = ($gwTask -and $mt5Task -and $wdTask -and (Test-Path $supervise) -and (Test-Path $watch) -and (Test-Path -LiteralPath $mt5Exe) -and ($null -ne $cf) -and ($cf.StartType -eq "Automatic"))
$softwareReady = $configReady
$rebootReady = ($softwareReady -and ($auto.State -eq "READY") -and ($provider.State -eq "READY"))

Write-Host ""
Write-Host ("SOFTWARE RECOVERY: {0}" -f $(if ($softwareReady) { "READY" } else { "ACTION_REQUIRED" }))
Write-Host ("AUTO_LOGON: {0}" -f $auto.State)
Write-Host ("PROVIDER POWER-LOSS: {0}" -f $provider.State)
Write-Host ("PROVIDER POWER RECOVERY: {0}" -f $provider.State)
Write-Host ("REBOOT READINESS: {0}" -f $(if ($rebootReady) { "READY" } else { "ACTION_REQUIRED" }))
Write-Host "REBOOT READINESS is READY only when AUTO_LOGON=READY and PROVIDER POWER RECOVERY=READY."
Write-Host "Repository code cannot enable Auto-Logon or provider power-on. Interactive tasks need a logged-on desktop."
Write-Host "This script does not reboot the host."
Write-Host "LIVE ORDER SENT: NO"
Write-Host "NO ORDER IS SENT."
Write-Host ("PASS={0} WARN={1} FAIL={2}" -f $Pass, $Warn, $Fail)
if ($Fail -gt 0) { exit 2 }
if (-not $rebootReady) { exit 0 }
exit 0
