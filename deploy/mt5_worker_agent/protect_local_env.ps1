# Restrict ACL on deploy/mt5_worker_agent/local.env to the current user.
# Does not print file contents. Creates an empty local.env from the example
# if missing (placeholders only — never invents credentials).
# Usage: .\deploy\mt5_worker_agent\protect_local_env.ps1

$ErrorActionPreference = "Stop"
$Dir = $PSScriptRoot
$EnvFile = Join-Path $Dir "local.env"
$Example = Join-Path $Dir "local.env.example"

if (-not (Test-Path $EnvFile)) {
  if (-not (Test-Path $Example)) {
    throw "local.env.example missing — cannot bootstrap local.env"
  }
  Copy-Item $Example $EnvFile
  Write-Host "Created local.env from example (placeholders only)"
}

# Remove inheritance; grant current user Modify; SYSTEM read for services if present.
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $EnvFile /inheritance:r | Out-Null
icacls $EnvFile /grant:r "${user}:(M)" | Out-Null
icacls $EnvFile /grant:r "SYSTEM:(R)" | Out-Null
Write-Host "ACL tightened on local.env for $user (contents not printed)"
icacls $EnvFile
