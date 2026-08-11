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

function Get-ListenPids {
  $pids = @()
  Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { $pids += $_.OwningProcess }
  return @($pids | Select-Object -Unique)
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

function Stop-GatewayPids {
  param([int[]]$TargetPids)
  foreach ($procId in $TargetPids) {
    if ($procId -le 0) { continue }
    Write-SupLog ("stopping gateway pid={0}" -f $procId)
    try {
      Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    } catch {}
  }
  Start-Sleep -Seconds 2
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
  Set-Content -Path $PidFile -Value $proc.Id -Encoding ASCII
  Write-SupLog ("gateway started pid={0}" -f $proc.Id)
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
  $listen = Get-ListenPids
  if ($listen.Count -eq 0) {
    return $false
  }
  if (Test-LiveOk) {
    Write-SupLog ("gateway already live on :{0} pids={1}" -f $Port, ($listen -join ","))
    Set-Content -Path $PidFile -Value $listen[0] -Encoding ASCII
    return $true
  }
  # Port occupied but process unresponsive - reclaim.
  Write-SupLog ("port {0} occupied but /health/live failed - reclaiming" -f $Port)
  Stop-GatewayPids -TargetPids $listen
  return $false
}

# --- main ---
Write-SupLog "supervisor begin Once=$Once"
if (Test-Path $StopFile) { Remove-Item $StopFile -Force }

$backoff = $RestartBackoffSec
$failStreak = 0

while ($true) {
  if (Test-Path $StopFile) {
    Write-SupLog "STOP file present - exiting supervisor"
    $listen = Get-ListenPids
    Stop-GatewayPids -TargetPids $listen
    exit 0
  }

  $healthy = Ensure-SingleHealthyInstance
  if (-not $healthy) {
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
      Write-SupLog "gateway process gone (no LISTEN on :$Port) - restart"
      break
    }

    if (-not (Test-LiveOk)) {
      $failStreak++
      Write-SupLog ("/health/live failed streak={0}/{1}" -f $failStreak, $UnresponsiveRestarts)
      if ($failStreak -ge $UnresponsiveRestarts) {
        Write-SupLog "gateway unresponsive - restarting process"
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
