# QuantForg MT5 Gateway supervisor (Windows production).
#
# Keeps the gateway as a long-running process that SURVIVES closing the
# PowerShell window that launched it (child started with WindowStyle Hidden).
#
# Features:
#   - single-instance lock (port 8765 + PID file)
#   - automatic restart after process exit / crash
#   - restart only when unresponsive (/health/live fails), NOT when quotes are slow
#   - clear rotating logs under docs/production/reports/gateway_supervisor/
#   - graceful stop via stop file or Ctrl+C on the supervisor loop
#
# Usage (foreground supervisor - safe for Task Scheduler "At log on"):
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\supervise_gateway.ps1
#
# One-shot start (no supervise loop):
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\supervise_gateway.ps1 -Once
#
# Register persistent Task Scheduler job:
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_gateway_task.ps1

param(
  [switch]$Once,
  [int]$HealthIntervalSec = 20,
  [int]$UnresponsiveRestarts = 3,
  [int]$RestartBackoffSec = 5,
  [int]$MaxBackoffSec = 60
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
  $RepoRoot = (Get-Location).Path
}
Set-Location $RepoRoot

$ReportDir = Join-Path $RepoRoot "docs\production\reports\gateway_supervisor"
$OutLog = Join-Path $ReportDir "gateway.out.log"
$ErrLog = Join-Path $ReportDir "gateway.err.log"
$SupLog = Join-Path $ReportDir "supervisor.log"
$PidFile = Join-Path $ReportDir "gateway.pid"
$StopFile = Join-Path $ReportDir "STOP"
$Port = 8765
$LiveUri = "http://127.0.0.1:$Port/health/live"
$HealthUri = "http://127.0.0.1:$Port/health"

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

$ProcessHelpers = Join-Path $PSScriptRoot "_gateway_process.ps1"
if (-not (Test-Path $ProcessHelpers)) {
  throw "Missing $ProcessHelpers"
}
. $ProcessHelpers

function Write-SupLog([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $msg
  Add-Content -Path $SupLog -Value $line -Encoding UTF8
  Write-Host $line
}

function Get-ProjectPython {
  $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) { return $venvPy }
  $info = & py -3.13 -m poetry env info -p 2>$null
  if ($LASTEXITCODE -eq 0 -and $info) {
    $candidate = Join-Path $info.Trim() "Scripts\python.exe"
    if (Test-Path $candidate) { return $candidate }
  }
  throw "Project venv not found. Run: py -3.13 -m poetry install"
}

function Test-PortListening {
  try {
    $props = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
    foreach ($ep in $props.GetActiveTcpListeners()) {
      if ($ep.Port -eq $Port) { return $true }
    }
  } catch {}
  return $false
}

function Get-ListenPids {
  return @(Get-GatewayListenPids)
}

function Save-GatewayPidState {
  $listen = @(Get-ListenPids)
  if ($listen.Count -eq 0) { return }
  $listener = $listen[0]
  $root = Get-GatewayTreeRoot -ProcessId $listener
  Write-GatewayPidFile -Path $PidFile -ListenerPid $listener -TreeRootPid $root
  Write-SupLog ("gateway tree adopted listener={0} tree_root={1}" -f $listener, $root)
}

function Stop-GatewayPids {
  param([int[]]$TargetPids)
  Write-SupLog "reclaim gateway process tree"
  Stop-GatewayProcessTree -ListenPids $TargetPids
}

function Test-LiveOk {
  try {
    $h = Invoke-RestMethod -Uri $LiveUri -TimeoutSec 3
    return ($h.status -eq "ok" -and $h.service -eq "mt5-gateway")
  } catch {
    return $false
  }
}

function Test-HealthReachable {
  # Process is responsive if /health returns within a short ceiling.
  # Degraded MT5 (connected=false) is NOT a restart reason.
  try {
    $null = Invoke-WebRequest -Uri $HealthUri -TimeoutSec 4 -UseBasicParsing
    return $true
  } catch {
    return $false
  }
}

function Rotate-LogIfLarge {
  param([string]$Path, [int]$MaxBytes = 5MB)
  if (-not (Test-Path $Path)) { return }
  $item = Get-Item $Path -ErrorAction SilentlyContinue
  if ($null -eq $item) { return }
  if ($item.Length -lt $MaxBytes) { return }
  $bak = "{0}.{1}.bak" -f $Path, (Get-Date -Format "yyyyMMddHHmmss")
  Move-Item -Path $Path -Destination $bak -Force
}

function Start-GatewayProcess {
  $Python = Get-ProjectPython
  Rotate-LogIfLarge -Path $OutLog
  Rotate-LogIfLarge -Path $ErrLog
  Rotate-LogIfLarge -Path $SupLog

  Write-SupLog ("starting gateway python={0}" -f $Python)
  $proc = Start-Process -FilePath $Python `
    -ArgumentList @("-m", "services.mt5_gateway.main") `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru
  Set-Content -Path $PidFile -Value ("tree_root={0}" -f $proc.Id) -Encoding ASCII
  Write-SupLog ("gateway started launcher={0}" -f $proc.Id)
  return $proc.Id
}

function Wait-GatewayReady {
  param([int]$TimeoutSec = 45)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    if (Test-LiveOk) { return $true }
    Start-Sleep -Seconds 1
  }
  return $false
}

function Ensure-SingleHealthyInstance {
  # HTTP first — connection-refused is immediate; do not wait on TCP table APIs.
  if (Test-LiveOk) {
    $listen = Get-ListenPids
    Write-SupLog ("gateway already live on 127.0.0.1:{0} listener_count={1} pids={2}" -f $Port, $listen.Count, ($listen -join ","))
    if ($listen.Count -gt 1) {
      Write-SupLog "independent listeners detected - reclaiming extra trees"
      Stop-GatewayPids -TargetPids $listen
      return $false
    }
    if ($listen.Count -eq 1) {
      Save-GatewayPidState
    }
    return $true
  }
  $listen = Get-ListenPids
  if ($listen.Count -eq 0) {
    return $false
  }
  Write-SupLog ("port {0} occupied but /health/live failed - reclaiming tree" -f $Port)
  Stop-GatewayPids -TargetPids $listen
  return $false
}

# --- main ---
$script:SupervisorMutex = New-Object System.Threading.Mutex(
  $false,
  "Global\QuantForgMT5GatewaySupervisor"
)
try {
  $owned = $script:SupervisorMutex.WaitOne(0)
} catch {
  $owned = $false
}
if (-not $owned) {
  Write-SupLog "duplicate supervisor prevented - mutex already held"
  exit 0
}

function Test-Mt5Process {
  $procs = @(Get-Process -Name "terminal64","terminal" -ErrorAction SilentlyContinue)
  return ($procs.Count -gt 0)
}

function Wait-Mt5Process {
  param([int]$TimeoutSec = 90)
  if (Test-Mt5Process) {
    Write-SupLog "mt5_detected"
    return $true
  }
  Write-SupLog "mt5_unavailable waiting up to ${TimeoutSec}s (Gateway will still start)"
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    if (Test-Path $StopFile) { return $false }
    if (Test-Mt5Process) {
      Write-SupLog "mt5_recovered"
      return $true
    }
    Start-Sleep -Seconds 2
  }
  Write-SupLog "mt5_unavailable still missing after wait - starting Gateway anyway"
  return $false
}

if (Test-Path $PidFile) {
  $staleLine = @(Get-Content $PidFile -ErrorAction SilentlyContinue | Where-Object { $_ -match "^(listener|tree_root)=" } | Select-Object -First 1)
  $stale = 0
  if ($staleLine -match "=(\d+)\s*$") { $stale = [int]$Matches[1] }
  if ($stale -le 0) {
    try { $stale = [int]((Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)) } catch { $stale = 0 }
  }
  if ($stale -gt 0) {
    $alive = Get-Process -Id $stale -ErrorAction SilentlyContinue
    if ($null -eq $alive) {
      Write-SupLog ("stale pid file removed pid={0}" -f $stale)
      Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
  }
}

Write-SupLog "supervisor start Once=$Once"
Write-SupLog "task_scheduler_startup pid=$PID repo=$RepoRoot"
if (Test-Path $StopFile) { Remove-Item $StopFile -Force }

$backoff = $RestartBackoffSec
$failStreak = 0
$mt5MissingLogged = $false

while ($true) {
  if (Test-Path $StopFile) {
    Write-SupLog "STOP file present - exiting supervisor"
    $listen = Get-ListenPids
    Stop-GatewayPids -TargetPids $listen
    exit 0
  }

  $healthy = Ensure-SingleHealthyInstance
  if (-not $healthy) {
    Wait-Mt5Process -TimeoutSec 90
    try {
      $null = Start-GatewayProcess
      if (-not (Wait-GatewayReady -TimeoutSec 45)) {
        Write-SupLog "gateway failed readiness (/health/live)"
        $failStreak++
        $listen = Get-ListenPids
        Stop-GatewayPids -TargetPids $listen
        Start-Sleep -Seconds $backoff
        $backoff = [Math]::Min($MaxBackoffSec, $backoff * 2)
        if ($Once) { exit 1 }
        continue
      }
      Write-SupLog "gateway ready"
      Save-GatewayPidState
      $backoff = $RestartBackoffSec
      $failStreak = 0
    } catch {
      Write-SupLog ("start failed: {0}" -f $_.Exception.Message)
      Start-Sleep -Seconds $backoff
      $backoff = [Math]::Min($MaxBackoffSec, $backoff * 2)
      if ($Once) { exit 1 }
      continue
    }
  }

  if ($Once) {
    Write-SupLog "Once mode - supervisor exiting (gateway remains running)"
    exit 0
  }

  # Watchdog: restart only when process dies or becomes unresponsive.
  while ($true) {
    if (Test-Path $StopFile) { break }

    $listen = Get-ListenPids
    if ($listen.Count -eq 0) {
      Write-SupLog "gateway restart recovery_attempt (process gone)"
      break
    }
    if ($listen.Count -gt 1) {
      Write-SupLog ("independent listeners={0} - reclaiming trees" -f ($listen -join ","))
      Stop-GatewayPids -TargetPids $listen
      break
    }
    if (Test-Mt5Process) {
      if ($mt5MissingLogged) {
        Write-SupLog "mt5_recovered"
        $mt5MissingLogged = $false
      }
    } else {
      if (-not $mt5MissingLogged) {
        Write-SupLog "mt5_unavailable (terminal process missing) - Gateway stays up"
        $mt5MissingLogged = $true
      }
    }

    if (-not (Test-LiveOk)) {
      $failStreak++
      Write-SupLog ("/health/live failed streak={0}/{1} (process unresponsive, not a market/Risk block)" -f $failStreak, $UnresponsiveRestarts)
      if ($failStreak -ge $UnresponsiveRestarts) {
        Write-SupLog "gateway restart recovery_attempt (unresponsive /health/live)"
        Stop-GatewayPids -TargetPids $listen
        $failStreak = 0
        break
      }
    } else {
      $failStreak = 0
      # Soft probe: log degraded MT5 without restarting for slow market data.
      if (-not (Test-HealthReachable)) {
        Write-SupLog "/health slow or unreachable while /health/live ok - not restarting (MT5 may be busy)"
      }
    }

    Start-Sleep -Seconds $HealthIntervalSec
  }

  Start-Sleep -Seconds $backoff
}
