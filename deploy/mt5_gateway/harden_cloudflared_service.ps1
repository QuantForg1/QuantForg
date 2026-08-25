# Idempotent Cloudflared SCM recovery actions. Does not log or read the tunnel token.
# Does not create a second Cloudflared service. Does not restart a healthy service.
# Does not place trades. Does not reboot.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\harden_cloudflared_service.ps1

$ErrorActionPreference = "Continue"
$HostHelpers = Join-Path $PSScriptRoot "_host_recovery.ps1"
if (-not (Test-Path $HostHelpers)) { throw "Missing $HostHelpers" }
. $HostHelpers

$svc = Get-CloudflaredService
if ($null -eq $svc) {
  Write-Host "FAIL: Cloudflared service not installed"
  exit 2
}

Write-Host ("service=Cloudflared status={0} start={1}" -f $svc.Status, $svc.StartType)
Write-Host ("command={0}" -f (Get-CloudflaredCommandSanitized))

if ($svc.StartType -ne "Automatic") {
  try {
    Set-Service -Name "Cloudflared" -StartupType Automatic -ErrorAction Stop
    Write-Host "Set Cloudflared StartType=Automatic"
  } catch {
    Write-Host "WARN: could not set Automatic (run elevated). Token not logged."
  }
}

$code = Set-CloudflaredScmRestartOnFailure
if ($code -ne 0) {
  Write-Host "WARN: sc.exe failure configuration returned $code (run elevated)"
} else {
  Write-Host "SCM recovery: restart on first/second/subsequent failure (60s delay, 24h reset)"
}

if (Test-CloudflaredScmRestartConfigured) {
  Write-Host "Cloudflared SCM restart actions: configured"
} else {
  Write-Host "WARN: could not confirm SCM restart actions"
}

$pids = @(Get-CloudflaredPids)
Write-Host ("cloudflared_process_count={0} (duplicates not killed)" -f $pids.Count)
if ($svc.Status -ne "Running") {
  Write-Host "Starting Cloudflared service (was not Running)"
  Start-Service -Name "Cloudflared"
}
Write-Host "Token file path is not printed. Token contents are never read by this script."
exit 0
