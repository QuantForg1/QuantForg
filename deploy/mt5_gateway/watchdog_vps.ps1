# Lightweight VPS watchdog — one pass per scheduled trigger.
# Recovers missing MT5 / Cloudflared / Gateway supervisor only.
# NEVER kills a healthy Gateway listener. NEVER sends broker orders.
# NEVER reads or logs gateway/tunnel tokens.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\watchdog_vps.ps1

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
  $RepoRoot = (Get-Location).Path
}
Set-Location $RepoRoot

$ReportDir = Join-Path $RepoRoot "docs\production\reports\gateway_supervisor"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$Log = Join-Path $ReportDir "watchdog.log"

$mutex = New-Object System.Threading.Mutex($false, "Global\QuantForgVpsWatchdog")
try {
  $owned = $mutex.WaitOne(0)
} catch {
  $owned = $false
}
if (-not $owned) {
  exit 0
}

function Write-Wd([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $msg
  Add-Content -Path $Log -Value $line -Encoding UTF8
}

$ProcessHelpers = Join-Path $PSScriptRoot "_gateway_process.ps1"
$HostHelpers = Join-Path $PSScriptRoot "_host_recovery.ps1"
if (Test-Path $ProcessHelpers) { . $ProcessHelpers }
if (Test-Path $HostHelpers) { . $HostHelpers }

Write-Wd "watchdog pass start"

# 1. MT5
if (Get-Command Test-Mt5TerminalProcess -ErrorAction SilentlyContinue) {
  if (-not (Test-Mt5TerminalProcess)) {
    Write-Wd "mt5_missing recovery_attempt start_mt5_terminal (no broker login)"
    $starter = Join-Path $PSScriptRoot "start_mt5_terminal.ps1"
    if (Test-Path $starter) {
      & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $starter
    }
  } else {
    Write-Wd "mt5_detected"
  }
}

# 2. Cloudflared — never Gateway first
if (Get-Command Test-CloudflaredServiceRunning -ErrorAction SilentlyContinue) {
  $cfPids = @(Get-CloudflaredPids)
  if ($cfPids.Count -gt 1) {
    Write-Wd ("cloudflared_duplicate count={0} - not killing" -f $cfPids.Count)
  }
  if (-not (Test-CloudflaredServiceRunning)) {
    Write-Wd "cloudflared_service_stopped recovery_attempt Start-Service"
    try {
      Start-Service -Name "Cloudflared" -ErrorAction Stop
      Write-Wd "cloudflared_start requested"
    } catch {
      Write-Wd ("cloudflared_start failed: {0}" -f $_.Exception.Message)
    }
  } else {
    Write-Wd "cloudflared_service running"
  }
}

# 3. Gateway: adopt healthy listener; else start scheduled supervisor (IgnoreNew)
$liveOk = $false
try {
  $h = Invoke-RestMethod "http://127.0.0.1:8765/health/live" -TimeoutSec 3
  $liveOk = ($h.status -eq "ok" -and $h.service -eq "mt5-gateway")
} catch {}
$listen = @()
if (Get-Command Get-GatewayListenPids -ErrorAction SilentlyContinue) {
  $listen = @(Get-GatewayListenPids)
}
if ($liveOk -and $listen.Count -eq 1) {
  Write-Wd ("gateway_healthy listener={0} - adopted not restarted" -f $listen[0])
} elseif ($listen.Count -gt 1) {
  Write-Wd ("gateway_duplicate_listeners count={0} - supervisor must reclaim; watchdog does not kill" -f $listen.Count)
} else {
  Write-Wd "gateway_unhealthy_or_missing recovery_attempt Start-ScheduledTask QuantForgMT5Gateway"
  try {
    Start-ScheduledTask -TaskName "QuantForgMT5Gateway" -ErrorAction Stop
  } catch {
    Write-Wd ("gateway_task_start failed: {0}" -f $_.Exception.Message)
  }
}

Write-Wd "watchdog pass end"
exit 0
