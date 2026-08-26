# Read-only Windows auto-logon readiness. Operator-owned.
# Possible AUTO_LOGON states: READY, ACTION_REQUIRED, NOT_SUPPORTED, ERROR.
# NEVER writes registry. NEVER stores credentials. NEVER places trades.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\inspect_autologon.ps1

$ErrorActionPreference = "Continue"
$HostHelpers = Join-Path $PSScriptRoot "_host_recovery.ps1"
if (-not (Test-Path $HostHelpers)) { throw "Missing $HostHelpers" }
. $HostHelpers

$info = Get-AutoLogonReadiness
$admin = Get-LocalAdministratorState
Write-Host "AUTO_LOGON inspection (password contents never read or printed)"
Write-Host ("State={0}" -f $info.State)
Write-Host ("AutoAdminLogon_enabled={0}" -f $info.Enabled)
Write-Host ("DefaultUserName_configured={0}" -f $info.UserConfigured)
Write-Host ("DefaultDomainName_configured={0}" -f $info.DomainConfigured)
if ($info.UserConfigured) {
  Write-Host ("DefaultUserName={0}" -f $info.DefaultUserName)
}
if ($info.DomainConfigured) {
  Write-Host ("DefaultDomainName={0}" -f $info.DefaultDomainName)
}
Write-Host ("Winlogon_secret_value_name_present={0} (contents not read)" -f $info.PasswordValuePresent)
Write-Host ("SecretStorage={0}" -f $info.SecretStorage)
Write-Host ("InteractiveUser={0}" -f $info.InteractiveUser)
Write-Host ("Administrator_exists={0} enabled={1} password_configured={2}" -f $admin.Exists, $admin.Enabled, $admin.PasswordConfigured)
if (-not [string]::IsNullOrWhiteSpace($info.AutologonBinary)) {
  Write-Host ("AutologonBinary={0}" -f $info.AutologonBinary)
} else {
  Write-Host "AutologonBinary=not_found_in_common_paths"
}
Write-Host ""
Write-Host ("AUTO_LOGON: {0}" -f $info.State)
if ($info.State -eq "READY") {
  if ($info.SecretStorage -eq "lsa_or_external") {
    Write-Host "LSA-protected or external secret is assumed; plaintext Winlogon secret value name is absent. This is READY."
  }
  exit 0
}
if ($info.State -eq "NOT_SUPPORTED") {
  Write-Host "Winlogon Auto-Logon is not available on this installation."
  exit 0
}
if ($info.State -eq "ERROR") {
  Write-Host "Winlogon could not be inspected (run elevated). Password was not read."
  exit 2
}
Write-Host "Repository scripts cannot enable Auto-Logon. Enter the password only in Sysinternals Autologon or netplwiz."
Write-Host "Operator action required: enter the Administrator password only in the Sysinternals Autologon Windows dialog."
Write-Host "One-command workflow:"
Write-Host "  powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\finalize_unattended_reboot.ps1"
Write-Host "Do not paste the password into git, chat, or these scripts."
exit 0
