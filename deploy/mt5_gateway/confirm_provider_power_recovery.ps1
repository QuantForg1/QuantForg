# Operator attestation that the VPS provider will restart the VM after power loss.
# Windows guest cannot read BIOS/hypervisor power-on policy. This file is not detection.
# NEVER stores passwords or tokens. NEVER reboots. NEVER places trades.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\confirm_provider_power_recovery.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\confirm_provider_power_recovery.ps1 -IConfirmTheProviderIsConfigured
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\confirm_provider_power_recovery.ps1 -Clear

param(
  [switch]$IConfirmTheProviderIsConfigured,
  [switch]$Clear
)

$ErrorActionPreference = "Stop"
$HostHelpers = Join-Path $PSScriptRoot "_host_recovery.ps1"
if (-not (Test-Path $HostHelpers)) { throw "Missing $HostHelpers" }
. $HostHelpers

$marker = Get-ProviderPowerMarkerPath
$dir = Split-Path -Parent $marker
Write-Host "Provider power recovery cannot be verified from inside Windows."
Write-Host "Confirm in the VPS panel / BIOS, then attest with -IConfirmTheProviderIsConfigured."
Write-Host "Checklist (operator, outside this VM):"
Write-Host "  - automatic VPS start after host reboot"
Write-Host "  - power-on-after-power-loss"
Write-Host "  - provider watchdog / auto-reboot"
Write-Host "  - BIOS/UEFI restore-after-power-loss if exposed"
Write-Host ("Marker={0}" -f $marker)

if ($Clear) {
  if (Test-Path -LiteralPath $marker) { Remove-Item -LiteralPath $marker -Force }
  Write-Host "PROVIDER POWER RECOVERY: UNKNOWN (attestation cleared)"
  exit 0
}

if ($IConfirmTheProviderIsConfigured) {
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  @(
    "confirmed=true",
    ("utc=" + (Get-Date).ToUniversalTime().ToString("o")),
    ("attested_by=" + $env:USERNAME),
    "source=operator_attestation",
    "note=Windows guest cannot verify hypervisor or BIOS power-on"
  ) | Set-Content -LiteralPath $marker -Encoding ASCII
  Write-Host "PROVIDER POWER RECOVERY: READY (operator attestation recorded; not a BIOS probe)"
  exit 0
}

$info = Get-ProviderPowerReadiness
Write-Host ("PROVIDER POWER RECOVERY: {0}" -f $info.State)
if ($info.State -ne "READY") {
  Write-Host "No attestation yet. After the provider panel is configured, re-run with -IConfirmTheProviderIsConfigured."
}
exit 0
