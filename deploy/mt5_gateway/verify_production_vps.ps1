# Local verification for a Windows MT5 Gateway host.
# NEVER calls order_send, NEVER places orders, NEVER modifies positions/SL/TP.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\verify_production_vps.ps1
#
# Optional -RepoRoot when not run from the clone.

param(
  [string]$RepoRoot = "",
  [string]$GatewayTaskName = "QuantForgMT5Gateway",
  [string]$TerminalTaskName = "QuantForgMT5Terminal",
  [string]$ExpectedTerminal = "C:\Program Files\MetaTrader 5\terminal64.exe"
)

$ErrorActionPreference = "Continue"
$Fail = 0
$Warn = 0
$Pass = 0
$supPid = 0
$listenerPid = 0
$listenerCount = 0
$treePids = @()
$Rows = New-Object System.Collections.Generic.List[object]

function Add-Check {
  param([string]$Name, [string]$Status, [string]$Detail)
  $Rows.Add([pscustomobject]@{ name = $Name; status = $Status; detail = $Detail })
  if ($Status -eq "FAIL") { $script:Fail++ }
  elseif ($Status -eq "WARN") { $script:Warn++ }
  else { $script:Pass++ }
}

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

$ProcessHelpers = Join-Path $PSScriptRoot "_gateway_process.ps1"
$HostHelpers = Join-Path $PSScriptRoot "_host_recovery.ps1"
if (Test-Path $HostHelpers) { . $HostHelpers }
if (Test-Path $ProcessHelpers) { . $ProcessHelpers }
if (Get-Command Resolve-Mt5TerminalPath -ErrorAction SilentlyContinue) {
  $resolvedMt5 = Resolve-Mt5TerminalPath -Preferred $ExpectedTerminal
  if (Test-Path -LiteralPath $resolvedMt5) { $ExpectedTerminal = $resolvedMt5 }
}
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
  Add-Check "repository_root" "FAIL" "pyproject.toml not found at $RepoRoot"
} else {
  Add-Check "repository_root" "PASS" $RepoRoot
}

$os = "unknown"
try { $os = [System.Environment]::OSVersion.VersionString } catch {}
if ($os -match "Windows") {
  Add-Check "windows" "PASS" $os
} else {
  Add-Check "windows" "FAIL" $os
}

$pyOk = $false
$pyVer = ""
try {
  $pyVer = (& py -3.13 --version 2>$null | Out-String).Trim()
  if ($pyVer -match "3\.13") { $pyOk = $true }
} catch {}
if ($pyOk) { Add-Check "python_3_13" "PASS" $pyVer } else { Add-Check "python_3_13" "FAIL" "py -3.13 not found" }

$poetryOk = $false
$poetryVer = ""
try {
  $poetryVer = (& py -3.13 -m poetry --version 2>$null | Out-String).Trim()
  if ($poetryVer -match "Poetry") { $poetryOk = $true }
} catch {}
if ($poetryOk) { Add-Check "poetry" "PASS" $poetryVer } else { Add-Check "poetry" "WARN" "Poetry not on py -3.13 (venv may still be valid)" }

$venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
  $venvVer = & $venvPy -c "import sys; print(sys.version.split()[0])"
  if ("$venvVer" -match "^3\.13") {
    Add-Check "venv" "PASS" "$venvPy ($venvVer)"
  } else {
    Add-Check "venv" "FAIL" "expected Python 3.13, got $venvVer"
  }
} else {
  Add-Check "venv" "FAIL" "missing $venvPy"
}

if (Test-Path $venvPy) {
  & $venvPy -c "import uvicorn, fastapi" 2>$null
  if ($LASTEXITCODE -eq 0) {
    Add-Check "gateway_deps" "PASS" "uvicorn+fastapi import ok"
  } else {
    Add-Check "gateway_deps" "FAIL" "uvicorn/fastapi missing in .venv"
  }
  & $venvPy -c "import MetaTrader5" 2>$null
  if ($LASTEXITCODE -eq 0) {
    Add-Check "metatrader5_package" "PASS" "MetaTrader5 import ok"
  } else {
    Add-Check "metatrader5_package" "FAIL" "MetaTrader5 package missing in .venv"
  }
}

if (Test-Path -LiteralPath $ExpectedTerminal) {
  Add-Check "mt5_executable" "PASS" $ExpectedTerminal
} else {
  Add-Check "mt5_executable" "FAIL" "not found: $ExpectedTerminal"
}

$mt5 = @(Get-Process -Name "terminal64","terminal" -ErrorAction SilentlyContinue)
if ($mt5.Count -eq 1) {
  Add-Check "mt5_process" "PASS" ("pid={0}" -f $mt5[0].Id)
} elseif ($mt5.Count -gt 1) {
  Add-Check "mt5_process" "WARN" ("duplicate terminals count={0}" -f $mt5.Count)
} else {
  Add-Check "mt5_process" "FAIL" "terminal64.exe not running"
}

$scripts = @(
  "deploy\mt5_gateway\supervise_gateway.ps1",
  "deploy\mt5_gateway\start_gateway.ps1",
  "deploy\mt5_gateway\install_gateway_task.ps1",
  "deploy\mt5_gateway\start_mt5_terminal.ps1",
  "deploy\mt5_gateway\_gateway_process.ps1",
  "deploy\mt5_gateway\_host_recovery.ps1",
  "deploy\mt5_gateway\watchdog_vps.ps1",
  "deploy\mt5_gateway\install_watchdog_task.ps1",
  "deploy\mt5_gateway\verify_reboot_readiness.ps1",
  "deploy\mt5_gateway\inspect_autologon.ps1",
  "deploy\mt5_gateway\open_autologon_ui.ps1",
  "deploy\mt5_gateway\confirm_provider_power_recovery.ps1",
  "deploy\mt5_gateway\finalize_unattended_reboot.ps1",
  "deploy\mt5_gateway\harden_cloudflared_service.ps1"
)
foreach ($rel in $scripts) {
  $p = Join-Path $RepoRoot $rel
  if (Test-Path $p) { Add-Check "script:$rel" "PASS" $p }
  else { Add-Check "script:$rel" "FAIL" "missing" }
}

$listenPids = @()
$listenerCount = 0
$listenerPid = 0
$treeRoot = 0
$treePids = @()
$independentRoots = @()
if (Test-Path $ProcessHelpers) {
  $listenPids = @(Get-GatewayListenPids)
  $listenerCount = $listenPids.Count
  if ($listenerCount -ge 1) {
    $listenerPid = $listenPids[0]
    $treeRoot = Get-GatewayTreeRoot -ProcessId $listenerPid
    $treePids = @(Get-GatewayTreePids -RootPid $treeRoot)
  }
  $independentRoots = @(Get-IndependentGatewayTreeRoots -ListenPids $listenPids)
}

$liveOk = $false
$liveVersion = ""
$liveProbe = ""
try {
  $live = Invoke-RestMethod "http://127.0.0.1:8765/health/live" -TimeoutSec 5
  if (Get-Command Test-GatewayLivePayload -ErrorAction SilentlyContinue) {
    $liveOk = Test-GatewayLivePayload -Payload $live
  } else {
    $liveOk = ($live.status -eq "ok" -and $live.service -eq "mt5-gateway")
  }
  $liveVersion = [string]$live.gateway_version
  if ($null -ne $live.PSObject.Properties["probe"]) { $liveProbe = [string]$live.probe }
} catch {}

if ($listenerCount -eq 1 -and $independentRoots.Count -le 1 -and $liveOk) {
  Add-Check "gateway_process" "PASS" ("listener_count=1 listener_pid={0} tree_root={1} tree={2}" -f $listenerPid, $treeRoot, ($treePids -join ","))
} elseif ($listenerCount -gt 1 -or $independentRoots.Count -gt 1) {
  Add-Check "gateway_process" "FAIL" ("independent Gateway trees listeners={0} roots={1}" -f ($listenPids -join ","), ($independentRoots -join ","))
} elseif ($listenerCount -eq 1 -and -not $liveOk) {
  Add-Check "gateway_process" "FAIL" ("listener_pid={0} but /health/live not OK" -f $listenerPid)
} else {
  Add-Check "gateway_process" "FAIL" "no LISTENING pid on 127.0.0.1:8765"
}

$listen = $false
try {
  $props = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
  foreach ($ep in $props.GetActiveTcpListeners()) {
    if ($ep.Port -eq 8765) { $listen = $true; break }
  }
} catch {}
if ($listen) { Add-Check "port_8765" "PASS" "LISTEN" } else { Add-Check "port_8765" "FAIL" "not listening" }

if ($liveOk) {
  Add-Check "health_live" "PASS" ("version={0} probe={1}" -f $liveVersion, $liveProbe)
} else {
  Add-Check "health_live" "FAIL" "http://127.0.0.1:8765/health/live not OK"
}

$health = $null
try {
  $health = Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 8
  $mt5c = $false
  if ($null -ne $health.mt5) { $mt5c = [bool]$health.mt5.connected }
  if ($health.status -eq "ok") {
    if ($mt5c) {
      Add-Check "health" "PASS" ("mt5.connected=true session={0}" -f $health.mt5.session_mode)
      $sess = [string]$health.mt5.session_mode
      if ($sess -eq "attached") {
        Add-Check "mt5_attached" "PASS" ("session_mode={0}" -f $sess)
      } else {
        Add-Check "mt5_attached" "WARN" ("connected=true session_mode={0}" -f $sess)
      }
    } else {
      Add-Check "health" "WARN" "gateway up but mt5.connected=false (normal if terminal still attaching)"
      Add-Check "mt5_attached" "WARN" "mt5.connected=false (do not restart a healthy Gateway for attach lag)"
    }
  } else {
    Add-Check "health" "FAIL" ("status={0}" -f $health.status)
    Add-Check "mt5_attached" "FAIL" "gateway /health status not ok"
  }
} catch {
  Add-Check "health" "FAIL" $_.Exception.Message
  Add-Check "mt5_attached" "FAIL" "/health not reachable"
}

function Test-Task {
  param([string]$Name)
  $t = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
  if ($null -eq $t) {
    Add-Check "task:$Name" "FAIL" "not registered"
    return
  }
  $info = Get-ScheduledTaskInfo -TaskName $Name -ErrorAction SilentlyContinue
  Add-Check "task:$Name" "PASS" ("state={0} last={1}" -f $t.State, $info.LastTaskResult)
}
Test-Task $GatewayTaskName
Test-Task $TerminalTaskName
$wd = Get-ScheduledTask -TaskName "QuantForgVpsWatchdog" -ErrorAction SilentlyContinue
$wdRepeatOk = $false
if ($null -eq $wd) {
  Add-Check "task:QuantForgVpsWatchdog" "WARN" "not registered (run install_watchdog_task.ps1)"
  Add-Check "watchdog_repetition" "WARN" "watchdog task missing"
} else {
  $wdInfo = Get-ScheduledTaskInfo -TaskName "QuantForgVpsWatchdog" -ErrorAction SilentlyContinue
  Add-Check "task:QuantForgVpsWatchdog" "PASS" ("state={0} last={1}" -f $wd.State, $wdInfo.LastTaskResult)
  foreach ($tr in @($wd.Triggers)) {
    if ($null -eq $tr.Repetition) { continue }
    $iv = [string]$tr.Repetition.Interval
    if ($iv -match "PT2M" -or $iv -match "^00:02:00") { $wdRepeatOk = $true }
  }
  if ($wdRepeatOk) {
    Add-Check "watchdog_repetition" "PASS" "2-minute Interval present"
  } else {
    Add-Check "watchdog_repetition" "FAIL" "expected PT2M / 00:02:00 repetition"
  }
}

$gwTask = Get-ScheduledTask -TaskName $GatewayTaskName -ErrorAction SilentlyContinue
if ($null -ne $gwTask -and [string]$gwTask.State -ne "Running" -and $liveOk) {
  Add-Check "gateway_task_runtime" "WARN" "QuantForgMT5Gateway not Running but local /health/live OK (watchdog is authoritative; Ready is not health)"
} elseif ($null -ne $gwTask -and [string]$gwTask.State -ne "Running" -and -not $liveOk) {
  Add-Check "gateway_task_runtime" "FAIL" "QuantForgMT5Gateway not Running and local /health/live failed"
} elseif ($null -ne $gwTask) {
  Add-Check "gateway_task_runtime" "PASS" ("state={0}" -f $gwTask.State)
}

$cfSvc = Get-Service -Name "Cloudflared" -ErrorAction SilentlyContinue
if ($null -eq $cfSvc) {
  Add-Check "cloudflared_service" "FAIL" "Cloudflared service not installed"
} elseif ($cfSvc.Status -eq "Running") {
  Add-Check "cloudflared_service" "PASS" ("status={0} start={1}" -f $cfSvc.Status, $cfSvc.StartType)
} else {
  Add-Check "cloudflared_service" "FAIL" ("status={0}" -f $cfSvc.Status)
}
$cfPids = @(Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue)
if ($cfPids.Count -eq 1) {
  Add-Check "cloudflared_process" "PASS" ("count=1 pid={0}" -f $cfPids[0].Id)
} elseif ($cfPids.Count -gt 1) {
  Add-Check "cloudflared_process" "WARN" ("duplicate cloudflared count={0}" -f $cfPids.Count)
} else {
  Add-Check "cloudflared_process" "FAIL" "cloudflared.exe not running"
}
if (Get-Command Get-CloudflaredCommandSanitized -ErrorAction SilentlyContinue) {
  Add-Check "cloudflared_command" "PASS" (Get-CloudflaredCommandSanitized)
}
if (Get-Command Test-CloudflaredScmRestartConfigured -ErrorAction SilentlyContinue) {
  if (Test-CloudflaredScmRestartConfigured) {
    Add-Check "cloudflared_scm_recovery" "PASS" "restart on failure configured"
  } else {
    Add-Check "cloudflared_scm_recovery" "WARN" "run harden_cloudflared_service.ps1 elevated"
  }
}

$publicLive = $false
try {
  $pl = Invoke-RestMethod "https://gateway.quantforg.com/health/live" -TimeoutSec 8
  if ($pl.status -eq "ok" -and $pl.service -eq "mt5-gateway") { $publicLive = $true }
} catch {}
if ($publicLive) {
  Add-Check "tunnel_public_live" "PASS" "https://gateway.quantforg.com/health/live"
} else {
  Add-Check "tunnel_public_live" "WARN" "public /health/live not reachable (local Gateway may still be healthy)"
}

$mt5Connected = $false
try {
  if ($null -ne $health.mt5) { $mt5Connected = [bool]$health.mt5.connected }
} catch {}
$hostState = "CRITICAL"
if ($listenerCount -eq 1 -and $liveOk -and $mt5.Count -ge 1 -and $cfSvc -and $cfSvc.Status -eq "Running") {
  if ($mt5Connected -and $publicLive -and $cfPids.Count -eq 1) { $hostState = "HEALTHY" }
  else { $hostState = "DEGRADED" }
}
Add-Check "host_state" $(if ($hostState -eq "CRITICAL") { "FAIL" } elseif ($hostState -eq "HEALTHY") { "PASS" } else { "WARN" }) $hostState

$sup = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match "supervise_gateway\.ps1" })
$supPid = 0
if ($sup.Count -eq 1) {
  $supPid = [int]$sup[0].ProcessId
  Add-Check "supervisor_process" "PASS" ("count=1 pid={0}" -f $supPid)
} elseif ($sup.Count -gt 1) {
  Add-Check "supervisor_process" "FAIL" ("competing supervisors count={0}" -f $sup.Count)
} else {
  Add-Check "supervisor_process" "WARN" "supervisor loop not seen (Once mode or Interactive session ended)"
}

$logDir = Join-Path $RepoRoot "docs\production\reports\gateway_supervisor"
$supLog = Join-Path $logDir "supervisor.log"
if (Test-Path $supLog) {
  Add-Check "supervisor_log" "PASS" $supLog
} else {
  Add-Check "supervisor_log" "WARN" "no supervisor.log yet"
}
$wdLog = Join-Path $logDir "watchdog.log"
if (Test-Path $wdLog) {
  Add-Check "watchdog_log" "PASS" $wdLog
} else {
  Add-Check "watchdog_log" "WARN" "no watchdog.log yet"
}

$auto = $null
if (Get-Command Get-AutoLogonReadiness -ErrorAction SilentlyContinue) {
  $auto = Get-AutoLogonReadiness
  if ($auto.State -eq "READY") {
    Add-Check "auto_logon" "PASS" ("READY user_configured={0}" -f $auto.UserConfigured)
  } else {
    Add-Check "auto_logon" "WARN" "ACTION_REQUIRED (operator-owned; password never printed)"
  }
}

$uniqueness = "PASS"
if ($listenerCount -ne 1 -or $independentRoots.Count -gt 1) {
  $uniqueness = "FAIL"
  Add-Check "process_uniqueness" "FAIL" ("listeners={0} roots={1}" -f $listenerCount, ($independentRoots -join ","))
} else {
  $extra = @()
  if ($mt5.Count -gt 1) { $extra += "mt5" }
  if ($cfPids.Count -gt 1) { $extra += "cloudflared" }
  if ($extra.Count -gt 0) {
    Add-Check "process_uniqueness" "WARN" ("gateway unique; extra=" + ($extra -join ","))
  } else {
    Add-Check "process_uniqueness" "PASS" "gateway=1 mt5<=1 cloudflared<=1"
  }
}

$rebootReady = $false
$provider = $null
if (Get-Command Get-ProviderPowerReadiness -ErrorAction SilentlyContinue) {
  $provider = Get-ProviderPowerReadiness
  if ($provider.State -eq "READY") {
    Add-Check "provider_power_recovery" "PASS" "READY (operator attestation)"
  } else {
    Add-Check "provider_power_recovery" "WARN" "UNKNOWN (Windows guest cannot read provider/BIOS power-on)"
  }
}
$configReady = ($null -ne $wd -and $wdRepeatOk -and (Test-Path (Join-Path $RepoRoot "deploy\mt5_gateway\watchdog_vps.ps1")) -and ($null -ne $cfSvc) -and ($cfSvc.StartType -eq "Automatic") -and (Test-Path -LiteralPath $ExpectedTerminal))
if ($null -ne $auto -and $auto.State -eq "READY" -and $null -ne $provider -and $provider.State -eq "READY" -and $configReady) { $rebootReady = $true }
if ($rebootReady) {
  Add-Check "reboot_readiness" "PASS" "READY"
} else {
  Add-Check "reboot_readiness" "WARN" "ACTION_REQUIRED until AUTO_LOGON=READY and PROVIDER POWER RECOVERY=READY"
}

$softwareReady = ($null -ne $wd -and $wdRepeatOk -and (Test-Path (Join-Path $RepoRoot "deploy\mt5_gateway\watchdog_vps.ps1")))
$hostHealthyClaim = ($hostState -eq "HEALTHY")
$publicHealthyClaim = $publicLive

Write-Host ""
Write-Host "QuantForg VPS verification (local host only - not a Railway probe)"
Write-Host ("RepoRoot={0}" -f $RepoRoot)
Write-Host ("supervisor PID={0}" -f $supPid)
Write-Host ("listener PID={0}" -f $listenerPid)
Write-Host ("Gateway process tree={0}" -f ($treePids -join ","))
Write-Host ("listener count={0}" -f $listenerCount)
Write-Host ("host_state={0}" -f $hostState)
foreach ($row in $Rows) {
  Write-Host ("[{0}] {1} - {2}" -f $row.status, $row.name, $row.detail)
}
Write-Host ""
Write-Host "--- HOST HEALTH ---"
Write-Host ("HOST HEALTHY: {0}" -f $(if ($hostHealthyClaim) { "YES" } else { "NO ($hostState)" }))
Write-Host "--- SOFTWARE RECOVERY ---"
Write-Host ("SOFTWARE RECOVERY READY: {0}" -f $(if ($softwareReady) { "YES" } else { "NO" }))
Write-Host "--- REBOOT READINESS ---"
Write-Host ("AUTO_LOGON: {0}" -f $(if ($null -ne $auto) { $auto.State } else { "ACTION_REQUIRED" }))
Write-Host ("PROVIDER POWER RECOVERY: {0}" -f $(if ($null -ne $provider) { $provider.State } else { "UNKNOWN" }))
Write-Host ("REBOOT READINESS: {0}" -f $(if ($rebootReady) { "READY" } else { "ACTION_REQUIRED" }))
Write-Host "REBOOT READINESS is READY only when AUTO_LOGON=READY and PROVIDER POWER RECOVERY=READY."
Write-Host "--- PUBLIC TUNNEL ---"
Write-Host ("PUBLIC TUNNEL HEALTHY: {0}" -f $(if ($publicHealthyClaim) { "YES" } else { "NO" }))
Write-Host "--- PROCESS UNIQUENESS ---"
Write-Host ("PROCESS UNIQUENESS: {0}" -f $uniqueness)
Write-Host "--- MT5 SESSION ---"
Write-Host ("MT5 attached/connected reported above as mt5_attached / health")
Write-Host ("LIVE ORDER SENT: NO")
Write-Host "QuantForg is hardened for unattended 24/7 operation and automatic recovery of supported software/process failures while Windows/VPS remains powered and available. Full unattended reboot recovery additionally requires operator/provider configuration such as Windows auto-logon and VPS provider auto-start/power-loss recovery."
Write-Host "This does not claim never-stop, guaranteed 24/7, or recovery while the VPS is powered off."
Write-Host "NO ORDER IS SENT."
Write-Host ""
Write-Host ("PASS={0} WARN={1} FAIL={2}" -f $Pass, $Warn, $Fail)
if ($Fail -gt 0) { exit 2 }
exit 0
