# Opens the Windows auto-logon UI. NEVER accepts a password argument.
# NEVER writes Winlogon secrets. NEVER prints credentials. NEVER places trades.
# This script cannot enable Auto-Logon by itself; the operator must complete the UI.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\open_autologon_ui.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\open_autologon_ui.ps1 -LaunchUi

param(
  [switch]$LaunchUi
)

$ErrorActionPreference = "Continue"
Write-Host "QuantForg cannot enable Windows Auto-Logon from repository code."
Write-Host "Interactive MT5/Gateway tasks need a logged-on desktop after reboot."
Write-Host "S4U/session-0 is not used (it would isolate Gateway from the MT5 terminal)."
Write-Host "This helper never asks for, stores, or logs a password."
Write-Host ""
Write-Host "Operator steps (complete in the Windows UI, not in this script):"
Write-Host "  1. Preferred: run Sysinternals Autologon.exe as Administrator (LSA-protected secret)."
Write-Host "  2. Or run netplwiz / control userpasswords2, uncheck 'Users must enter a user name and password',"
Write-Host "     then enter the password only in that Windows dialog."
Write-Host "  3. Re-run inspect_autologon.ps1 until AUTO_LOGON: READY."
Write-Host "Do not paste the password into PowerShell, git, chat, .env, or task XML."
Write-Host ""

if ($LaunchUi) {
  $netplwiz = Join-Path $env:SystemRoot "System32\netplwiz.exe"
  if (Test-Path -LiteralPath $netplwiz) {
    Write-Host "Launching netplwiz.exe (password stays in the Windows dialog)."
    Start-Process -FilePath $netplwiz
  } else {
    Write-Host "Launching control userpasswords2"
    Start-Process -FilePath "control.exe" -ArgumentList "userpasswords2"
  }
} else {
  Write-Host "UI not launched. Re-run with -LaunchUi to open netplwiz (still no password argument)."
}

$candidates = @(
  (Join-Path $env:SystemRoot "Sysinternals\Autologon.exe"),
  "C:\Tools\Autologon.exe",
  "C:\Sysinternals\Autologon.exe"
)
$found = $false
foreach ($c in $candidates) {
  if (Test-Path -LiteralPath $c) {
    Write-Host ("Autologon.exe present at {0} (not launched; run it yourself as Administrator)." -f $c)
    $found = $true
    break
  }
}
if (-not $found) {
  Write-Host "Autologon.exe not in common local paths. Download from Microsoft Sysinternals if you prefer LSA storage."
}
exit 0
