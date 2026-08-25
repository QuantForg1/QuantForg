# Shared VPS host recovery helpers (MT5 process, Cloudflared service).
# Dot-source from supervise/watchdog/verify/recover.
# NEVER sends broker orders. NEVER reads or logs tunnel/gateway tokens.

$script:CloudflaredServiceName = "Cloudflared"
$script:PublicLiveUri = "https://gateway.quantforg.com/health/live"

function Test-Mt5TerminalProcess {
  $procs = @(Get-Process -Name "terminal64","terminal" -ErrorAction SilentlyContinue)
  return ($procs.Count -gt 0)
}

function Get-Mt5TerminalPids {
  $procs = @(Get-Process -Name "terminal64","terminal" -ErrorAction SilentlyContinue)
  return @($procs | ForEach-Object { [int]$_.Id })
}

function Get-CloudflaredService {
  return Get-Service -Name $script:CloudflaredServiceName -ErrorAction SilentlyContinue
}

function Test-CloudflaredServiceRunning {
  $svc = Get-CloudflaredService
  if ($null -eq $svc) { return $false }
  return ($svc.Status -eq "Running")
}

function Get-CloudflaredPids {
  $procs = @(Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue)
  return @($procs | ForEach-Object { [int]$_.Id })
}

function Get-HostHealthState {
  param(
    [int]$ListenerCount,
    [bool]$LiveOk,
    [bool]$Mt5Connected,
    [bool]$Mt5Process,
    [bool]$CloudflaredRunning,
    [int]$CloudflaredCount,
    [bool]$PublicLiveOk
  )
  if ($ListenerCount -ne 1 -or -not $LiveOk -or -not $Mt5Process -or -not $CloudflaredRunning) {
    return "CRITICAL"
  }
  if ($ListenerCount -eq 1 -and $LiveOk -and $Mt5Process -and $CloudflaredRunning -and $Mt5Connected -and $PublicLiveOk -and $CloudflaredCount -eq 1) {
    return "HEALTHY"
  }
  return "DEGRADED"
}

function Test-PublicGatewayLive {
  param([int]$TimeoutSec = 8)
  try {
    $h = Invoke-RestMethod -Uri $script:PublicLiveUri -TimeoutSec $TimeoutSec
    return ($h.status -eq "ok" -and $h.service -eq "mt5-gateway")
  } catch {
    return $false
  }
}
