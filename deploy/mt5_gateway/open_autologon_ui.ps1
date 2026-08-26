# Opens Sysinternals Autologon (preferred) or netplwiz. NEVER accepts a password argument.
# NEVER writes Winlogon secrets. NEVER prints credentials. NEVER places trades.
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

$computer = [string]$env:COMPUTERNAME
Write-Host "QuantForg cannot enable Windows Auto-Logon from repository code."
Write-Host "Interactive MT5/Gateway tasks need a logged-on desktop after reboot."
Write-Host "S4U/session-0 is not used (it would isolate Gateway from the MT5 terminal)."
Write-Host "This helper never asks for, stores, or logs a password."
Write-Host ""
Write-Host "If the Autologon dialog appears, set:"
Write-Host "  Username = Administrator"
Write-Host ("  Domain   = {0}" -f $computer)
Write-Host "  Password = enter only in that dialog, then Enable."
Write-Host "Do not paste the password into PowerShell, git, chat, .env, or task XML."
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
if (Test-Path -LiteralPath $netplwiz) {
  if ($Wait) { Start-Process -FilePath $netplwiz -Wait }
  else { Start-Process -FilePath $netplwiz }
} else {
  if ($Wait) { Start-Process -FilePath "control.exe" -ArgumentList "userpasswords2" -Wait }
  else { Start-Process -FilePath "control.exe" -ArgumentList "userpasswords2" }
}
exit 0
