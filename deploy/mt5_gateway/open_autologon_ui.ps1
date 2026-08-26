# Opens Sysinternals Autologon (preferred) or netplwiz. NEVER accepts a password argument.
# NEVER writes Winlogon passwords/AutoAdminLogon. May write non-secret DefaultUserName/DefaultDomainName=.
# This script cannot enable Auto-Logon by itself; the operator must complete the UI.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\open_autologon_ui.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\open_autologon_ui.ps1 -LaunchUi

param(
  [switch]$LaunchUi,
  [switch]$Wait
)

$ErrorActionPreference = "Continue"
$HostHelpers = Join-Path $PSScriptRoot "_host_recovery.ps1"
if (Test-Path $HostHelpers) { . $HostHelpers }

Write-Host "QuantForg cannot enable Windows Auto-Logon from repository code."
Write-Host "Interactive MT5/Gateway tasks need a logged-on desktop after reboot."
Write-Host "S4U/session-0 is not used (it would isolate Gateway from the MT5 terminal)."
Write-Host "This helper never asks for, stores, or logs a password."
Write-Host ""
if (Get-Command Write-AutologonOperatorInstructions -ErrorAction SilentlyContinue) {
  Write-AutologonOperatorInstructions
} else {
  Write-Host "If the Autologon dialog appears, set Username=Administrator Domain=. then Enable."
}
Write-Host ""

$autoBin = ""
if (Get-Command Get-SysinternalsAutologonPath -ErrorAction SilentlyContinue) {
  $autoBin = Get-SysinternalsAutologonPath
}

if (-not $LaunchUi) {
  if (-not [string]::IsNullOrWhiteSpace($autoBin)) {
    Write-Host ("Autologon binary present: {0} (not launched; pass -LaunchUi)" -f $autoBin)
  } else {
    Write-Host "Autologon binary not in common local paths. Pass -LaunchUi to open netplwiz as fallback."
  }
  exit 0
}

if (-not [string]::IsNullOrWhiteSpace($autoBin)) {
  $ready = $null
  if (Get-Command Get-AutoLogonReadiness -ErrorAction SilentlyContinue) {
    $ready = Get-AutoLogonReadiness
  }
  if ($null -eq $ready -or $ready.State -ne "READY") {
    if (Get-Command Set-AutologonNonSecretIdentity -ErrorAction SilentlyContinue) {
      $prefilled = Set-AutologonNonSecretIdentity
      Write-Host ("Non-secret identity prefill Username=Administrator Domain=. applied={0}" -f $prefilled)
    }
  }
  Write-Host ("Launching {0} (no password argument; GUI only)." -f $autoBin)
  if ($Wait) {
    Start-Process -FilePath $autoBin -Wait
  } else {
    Start-Process -FilePath $autoBin
  }
  exit 0
}

$netplwiz = Join-Path $env:SystemRoot "System32\netplwiz.exe"
Write-Host "Sysinternals Autologon not found. Falling back to netplwiz (password stays in the Windows dialog)."
if (Get-Command Get-AutoLogonReadiness -ErrorAction SilentlyContinue) {
  $ready = Get-AutoLogonReadiness
  if ($ready.State -ne "READY" -and (Get-Command Set-AutologonNonSecretIdentity -ErrorAction SilentlyContinue)) {
    $prefilled = Set-AutologonNonSecretIdentity
    Write-Host ("Non-secret identity prefill Username=Administrator Domain=. applied={0}" -f $prefilled)
  }
}
if (Test-Path -LiteralPath $netplwiz) {
  if ($Wait) { Start-Process -FilePath $netplwiz -Wait }
  else { Start-Process -FilePath $netplwiz }
} else {
  if ($Wait) { Start-Process -FilePath "control.exe" -ArgumentList "userpasswords2" -Wait }
  else { Start-Process -FilePath "control.exe" -ArgumentList "userpasswords2" }
}
exit 0
