# Real demo verification for one broker (exness|hfm|weltrade).
# Requires approved QF_DEMO_<BROKER>_* credentials in local.env — never invents success.
# Usage: .\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker exness -Slot demo-a

param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("exness", "hfm", "weltrade")]
  [string]$Broker,
  [string]$Slot = "demo-a",
  [switch]$AlsoRejectTest
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
  $Root = (Get-Location).Path
}
Set-Location $Root

$EnvFile = Join-Path $PSScriptRoot "local.env"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    if ($_ -match '^([^=]+)=(.*)$') {
      Set-Item -Path "Env:$($Matches[1].Trim())" -Value $Matches[2].Trim()
    }
  }
}

Write-Host "Verifying broker=$Broker slot=$Slot (passwords never printed)"
poetry run python -m services.mt5_worker_agent.main verify-broker --broker $Broker --slot $Slot
$code = $LASTEXITCODE
if ($AlsoRejectTest) {
  Write-Host "Running invalid-credential rejection test"
  poetry run python -m services.mt5_worker_agent.main reject-demo --broker $Broker --slot $Slot
}
exit $code
