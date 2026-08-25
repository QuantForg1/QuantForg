# Read-only Windows auto-logon readiness. Operator-owned. NEVER prints DefaultPassword.
# NEVER writes registry. NEVER stores credentials. NEVER places trades.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\inspect_autologon.ps1

$ErrorActionPreference = "Continue"
$HostHelpers = Join-Path $PSScriptRoot "_host_recovery.ps1"
if (-not (Test-Path $HostHelpers)) { throw "Missing $HostHelpers" }
. $HostHelpers

$info = Get-AutoLogonReadiness
Write-Host "AUTO_LOGON inspection (values only; password never read or printed)"
Write-Host ("State={0}" -f $info.State)
Write-Host ("AutoAdminLogon_enabled={0}" -f $info.Enabled)
Write-Host ("DefaultUserName_configured={0}" -f $info.UserConfigured)
if ($info.UserConfigured) {
  Write-Host ("DefaultUserName={0}" -f $info.DefaultUserName)
}
Write-Host ("DefaultPassword_value_present={0} (contents not read)" -f $info.PasswordValuePresent)
Write-Host ("InteractiveUser={0}" -f $info.InteractiveUser)
Write-Host ""
if ($info.State -eq "READY") {
  Write-Host "AUTO_LOGON: READY"
  exit 0
}
Write-Host "AUTO_LOGON: ACTION_REQUIRED"
Write-Host "Repository scripts cannot enable Auto-Logon. That requires the operator's Windows password in a Windows UI."
Write-Host "This helper never accepts, stores, or prints that password."
Write-Host "Open the UI (no password argument):"
Write-Host "  powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\open_autologon_ui.ps1 -LaunchUi"
Write-Host "Then complete Autologon.exe (preferred, LSA) or netplwiz, and re-run this inspect script."
Write-Host "Do not paste the password into git, chat, or these scripts."
exit 0
