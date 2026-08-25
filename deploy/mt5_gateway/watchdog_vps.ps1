# QuantForg VPS watchdog — one idempotent pass per Task Scheduler firing.
# Authoritative recovery for Gateway/MT5/Cloudflared. Not a permanent daemon.
# NEVER kills a healthy Gateway listener. NEVER sends broker orders.
# NEVER reads or logs gateway/tunnel tokens.
# NEVER blindly kill processes by image name (python, terminal64, cloudflared).
#
# Health is listener + /health/live, NOT QuantForgMT5Gateway Task Scheduler State=Ready/Running.
# If the Gateway task is Ready but :8765 is down, this script starts the Gateway process itself.
#
# Exit 0 = healthy or recovery succeeded
# Exit 1 = recovery attempted, Gateway still unhealthy
# Exit 2 = missing scripts / configuration error
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
$StateFile = Join-Path $ReportDir "watchdog.state"
$GwOut = Join-Path $ReportDir "watchdog_gateway.out.log"
$GwErr = Join-Path $ReportDir "watchdog_gateway.err.log"
$PidFile = Join-Path $ReportDir "gateway.pid"
$exitCode = 0

$mutex = New-Object System.Threading.Mutex($false, "Global\QuantForgVpsWatchdog")
try {
  $owned = $mutex.WaitOne(0)
} catch {
  $owned = $false
}
if (-not $owned) {
  try { $mutex.Dispose() } catch {}
  exit 0
}

function Write-Wd([string]$component, [string]$action, [string]$reason, [string]$result) {
  $line = "[{0}] component={1} action={2} reason={3} result={4}" -f `
    (Get-Date).ToUniversalTime().ToString("o"), $component, $action, $reason, $result
  Add-Content -Path $Log -Value $line -Encoding UTF8
}

function Rotate-WdLog {
  param([string]$Path, [int]$MaxBytes = 5MB)
  if (-not (Test-Path $Path)) { return }
  $item = Get-Item $Path -ErrorAction SilentlyContinue
  if ($null -eq $item -or $item.Length -lt $MaxBytes) { return }
  $bak = "{0}.{1}.bak" -f $Path, (Get-Date -Format "yyyyMMddHHmmss")
  Move-Item -Path $Path -Destination $bak -Force
}

try {
  $ProcessHelpers = Join-Path $PSScriptRoot "_gateway_process.ps1"
  $HostHelpers = Join-Path $PSScriptRoot "_host_recovery.ps1"
  if (-not (Test-Path $ProcessHelpers) -or -not (Test-Path $HostHelpers)) {
    Write-Wd "watchdog" "abort" "missing_helpers" "exit_2"
    $exitCode = 2
  } else {
    . $ProcessHelpers
    . $HostHelpers

    Rotate-WdLog -Path $Log
    Write-Wd "watchdog" "start" "scheduled_pass" "ok"

    function Test-LocalLive {
      return (Test-LocalGatewayLiveOk -TimeoutSec 3)
    }

    function Get-Listen {
      return @(Get-GatewayListenPids)
    }

    function Start-WatchdogGateway {
      $counters = Get-WatchdogStartCounters -StateFile $StateFile
      if (-not (Test-WatchdogGatewayStartAllowed -StateFile $StateFile -MaxPerHour 8)) {
        Write-Wd "gateway" "start" "restart_storm_prevented" ("starts={0} max=8" -f $counters.Starts)
        return $false
      }
      $venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
      if (-not (Test-Path $venvPy)) {
        Write-Wd "gateway" "start" "venv_missing" "fail"
        return $false
      }
      Rotate-WdLog -Path $GwOut
      Rotate-WdLog -Path $GwErr
      $oldListen = @(Get-Listen)
      $t0 = Get-Date
      Write-Wd "gateway" "start" "local_unhealthy_or_missing" ("old_listener={0}" -f ($(if ($oldListen.Count -gt 0) { $oldListen[0] } else { 0 })))
      $proc = Start-Process -FilePath $venvPy `
        -ArgumentList @("-m", "services.mt5_gateway.main") `
        -WorkingDirectory $RepoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $GwOut `
        -RedirectStandardError $GwErr `
        -PassThru
      $script:WatchdogStarts = $counters.Starts + 1
      $script:WatchdogWindowUtc = $counters.WindowUtc
      Write-Wd "gateway" "start" "launcher" ("pid={0}" -f $proc.Id)
      $deadline = (Get-Date).AddSeconds(45)
      while ((Get-Date) -lt $deadline) {
        if (Test-LocalLive) {
          $listenNow = Get-Listen
          if ($listenNow.Count -eq 1) {
            $root = Get-GatewayTreeRoot -ProcessId $listenNow[0]
            Write-GatewayPidFile -Path $PidFile -ListenerPid $listenNow[0] -TreeRootPid $root -Health "live_ok"
            $ms = [int]((Get-Date) - $t0).TotalMilliseconds
            Write-Wd "gateway" "ready" "health_live" ("listener={0} duration_ms={1}" -f $listenNow[0], $ms)
            return $true
          }
        }
        Start-Sleep -Seconds 1
      }
      Write-Wd "gateway" "start" "health_live_timeout" "fail"
      return $false
    }

    $script:WatchdogStarts = 0
    $script:WatchdogWindowUtc = [datetime]::UtcNow
    $existingCounters = Get-WatchdogStartCounters -StateFile $StateFile
    $script:WatchdogStarts = $existingCounters.Starts
    $script:WatchdogWindowUtc = $existingCounters.WindowUtc

    # 1. MT5 — never duplicate terminal64; no broker login
    $mt5Pids = @(Get-Mt5TerminalPids)
    if ($mt5Pids.Count -gt 1) {
      Write-Wd "mt5" "observe" "duplicate_terminal" ("count={0} not_killing" -f $mt5Pids.Count)
    }
    if (Test-Mt5TerminalProcess) {
      Write-Wd "mt5" "preserve" "terminal_running" ("pids={0}" -f ($mt5Pids -join ","))
    } else {
      Write-Wd "mt5" "recover" "process_missing" "start_mt5_terminal"
      $starter = Join-Path $PSScriptRoot "start_mt5_terminal.ps1"
      if (Test-Path $starter) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File $starter
      }
      $mt5Deadline = (Get-Date).AddSeconds(20)
      while ((Get-Date) -lt $mt5Deadline) {
        if (Test-Mt5TerminalProcess) { break }
        Start-Sleep -Seconds 2
      }
      if (Test-Mt5TerminalProcess) {
        Write-Wd "mt5" "recover" "started" "ok"
      } else {
        Write-Wd "mt5" "recover" "still_missing" "degraded"
      }
    }

    # 2. Local Gateway — Task Scheduler Ready is NOT health
    $liveOk = Test-LocalLive
    $listen = Get-Listen

    if ($liveOk -and $listen.Count -eq 1) {
      Write-Wd "gateway" "preserve" "live_ok_one_listener" "adopted not restarted"
    } elseif ($listen.Count -gt 1) {
      Write-Wd "gateway" "reclaim" "duplicate_listeners" ("count={0}" -f $listen.Count)
      $keepRoot = Get-GatewayTreeRoot -ProcessId $listen[0]
      $extraListen = @()
      foreach ($lp in $listen) {
        $r = Get-GatewayTreeRoot -ProcessId $lp
        if ($r -ne $keepRoot) { $extraListen += $lp }
      }
      if ($extraListen.Count -gt 0) {
        Stop-GatewayProcessTree -ListenPids $extraListen
        Start-Sleep -Seconds 2
      }
      $liveOk = Test-LocalLive
      $listen = Get-Listen
      if ($liveOk -and $listen.Count -eq 1) {
        Write-Wd "gateway" "reclaim" "kept_one_healthy" ("listener={0}" -f $listen[0])
      } else {
        Stop-GatewayProcessTree -ListenPids (Get-Listen)
        if (-not (Start-WatchdogGateway)) { $exitCode = 1 }
      }
    } elseif ($listen.Count -eq 1 -and -not $liveOk) {
      Write-Wd "gateway" "reclaim" "listener_unhealthy" ("listener={0}" -f $listen[0])
      Stop-GatewayProcessTree -ListenPids $listen
      if (-not (Start-WatchdogGateway)) { $exitCode = 1 }
    } else {
      Write-Wd "gateway" "recover" "no_listener_or_live_fail" "start_process"
      if (-not (Start-WatchdogGateway)) { $exitCode = 1 }
    }

    # Re-arm long-running supervisor only if it is not already running.
    # IgnoreNew + LastTaskResult=1 must not block process-level recovery above.
    $sup = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match "supervise_gateway\.ps1" })
    if ($sup.Count -eq 0) {
      try {
        Start-ScheduledTask -TaskName "QuantForgMT5Gateway" -ErrorAction SilentlyContinue
        Write-Wd "supervisor" "rearm" "task_not_running" "Start-ScheduledTask"
      } catch {
        Write-Wd "supervisor" "rearm" "task_start_failed" "ignored_health_is_live"
      }
    } else {
      Write-Wd "supervisor" "preserve" "process_running" ("pid={0}" -f $sup[0].ProcessId)
    }

    # 3. Cloudflared — do not restart Gateway for public-only failure
    $cfPids = @(Get-CloudflaredPids)
    if ($cfPids.Count -gt 1) {
      Write-Wd "cloudflared" "observe" "cloudflared_duplicate" ("count={0} not_killing" -f $cfPids.Count)
    }
    if (Test-CloudflaredServiceRunning) {
      Write-Wd "cloudflared" "preserve" "service_running" "ok"
    } else {
      Write-Wd "cloudflared" "recover" "service_stopped" "Start-Service"
      try {
        Start-Service -Name "Cloudflared" -ErrorAction Stop
        Write-Wd "cloudflared" "recover" "start_requested" "ok"
      } catch {
        Write-Wd "cloudflared" "recover" "start_failed" "fail"
      }
    }

    $liveOk = Test-LocalLive
    $listen = Get-Listen
    $publicOk = Test-PublicGatewayLive
    if ($liveOk -and $listen.Count -eq 1 -and -not $publicOk) {
      Write-Wd "tunnel" "observe" "local_ok_public_fail" "not_restarting_gateway"
      if (-not (Test-CloudflaredServiceRunning)) {
        try { Start-Service -Name "Cloudflared" -ErrorAction Stop } catch {}
      }
    } elseif ($publicOk) {
      Write-Wd "tunnel" "observe" "public_live_ok" "ok"
    }

    if (-not ($liveOk -and $listen.Count -eq 1)) {
      $exitCode = 1
      Write-Wd "watchdog" "end" "gateway_still_unhealthy" ("exit={0}" -f $exitCode)
    } else {
      $exitCode = 0
      Write-Wd "watchdog" "end" "healthy_or_recovered" ("exit={0} listener={1}" -f $exitCode, $listen[0])
    }

    @(
      ("utc=" + (Get-Date).ToUniversalTime().ToString("o")),
      ("live_ok=" + $liveOk),
      ("listener_count=" + $listen.Count),
      ("public_ok=" + $publicOk),
      ("exit=" + $exitCode),
      ("start_window_utc=" + $script:WatchdogWindowUtc.ToUniversalTime().ToString("o")),
      ("starts_in_window=" + $script:WatchdogStarts)
    ) | Set-Content -Path $StateFile -Encoding ASCII
  }
} catch {
  Write-Wd "watchdog" "error" "unhandled" $_.Exception.GetType().Name
  $exitCode = 2
} finally {
  try { $mutex.ReleaseMutex() | Out-Null } catch {}
  try { $mutex.Dispose() } catch {}
}

exit $exitCode
