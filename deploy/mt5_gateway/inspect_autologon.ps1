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
Write-Host "Interactive Scheduled Tasks need an interactive session after reboot."
Write-Host "Operator procedure (pick one; this repo never stores the password):"
Write-Host "  1. Sysinternals Autologon.exe (encrypts the secret in LSA) — preferred."
Write-Host "  2. netplwiz / control userpasswords2 — uncheck 'Users must enter a user name and password'."
Write-Host "Do not paste the password into git, chat, or these scripts."
exit 0
