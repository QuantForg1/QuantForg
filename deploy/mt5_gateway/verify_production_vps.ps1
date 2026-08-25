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
  "deploy\mt5_gateway\start_mt5_terminal.ps1"
)
foreach ($rel in $scripts) {
  $p = Join-Path $RepoRoot $rel
  if (Test-Path $p) { Add-Check "script:$rel" "PASS" $p }
  else { Add-Check "script:$rel" "FAIL" "missing" }
}

$gw = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match "services\.mt5_gateway\.main" })
if ($gw.Count -eq 1) {
  Add-Check "gateway_process" "PASS" ("pid={0}" -f $gw[0].ProcessId)
} elseif ($gw.Count -gt 1) {
  Add-Check "gateway_process" "FAIL" ("duplicate gateway processes count={0}" -f $gw.Count)
} else {
  Add-Check "gateway_process" "FAIL" "services.mt5_gateway.main not running"
}

$listen = $false
try {
  $props = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
  foreach ($ep in $props.GetActiveTcpListeners()) {
    if ($ep.Port -eq 8765) { $listen = $true; break }
  }
} catch {}
if ($listen) { Add-Check "port_8765" "PASS" "LISTEN" } else { Add-Check "port_8765" "FAIL" "not listening" }

try {
  $live = Invoke-RestMethod "http://127.0.0.1:8765/health/live" -TimeoutSec 5
  if ($live.status -eq "ok" -and $live.service -eq "mt5-gateway") {
    Add-Check "health_live" "PASS" ("version={0}" -f $live.gateway_version)
  } else {
    Add-Check "health_live" "FAIL" ($live | ConvertTo-Json -Compress)
  }
} catch {
  Add-Check "health_live" "FAIL" $_.Exception.Message
}

try {
  $health = Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 8
  $mt5c = $false
  if ($null -ne $health.mt5) { $mt5c = [bool]$health.mt5.connected }
  if ($health.status -eq "ok") {
    if ($mt5c) {
      Add-Check "health" "PASS" ("mt5.connected=true session={0}" -f $health.mt5.session_mode)
    } else {
      Add-Check "health" "WARN" "gateway up but mt5.connected=false (normal if terminal still attaching)"
    }
  } else {
    Add-Check "health" "FAIL" ("status={0}" -f $health.status)
  }
} catch {
  Add-Check "health" "FAIL" $_.Exception.Message
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

$sup = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match "supervise_gateway\.ps1" })
if ($sup.Count -ge 1) {
  if ($sup.Count -eq 1) {
    Add-Check "supervisor_process" "PASS" ("pid={0}" -f $sup[0].ProcessId)
  } else {
    Add-Check "supervisor_process" "WARN" ("multiple supervise_gateway.ps1 count={0}" -f $sup.Count)
  }
} else {
  Add-Check "supervisor_process" "WARN" "supervisor loop not seen (Once mode or task delay is ok if gateway is live)"
}

$logDir = Join-Path $RepoRoot "docs\production\reports\gateway_supervisor"
$supLog = Join-Path $logDir "supervisor.log"
if (Test-Path $supLog) {
  Add-Check "supervisor_log" "PASS" $supLog
} else {
  Add-Check "supervisor_log" "WARN" "no supervisor.log yet"
}

Write-Host ""
Write-Host "QuantForg VPS verification (local host only - not a Railway probe)"
Write-Host ("RepoRoot={0}" -f $RepoRoot)
foreach ($row in $Rows) {
  Write-Host ("[{0}] {1} - {2}" -f $row.status, $row.name, $row.detail)
}
Write-Host ""
Write-Host ("PASS={0} WARN={1} FAIL={2}" -f $Pass, $Warn, $Fail)
if ($Fail -gt 0) { exit 2 }
exit 0
