# Real demo/live verification for one broker on the existing Windows host.
# Requires approved QF_DEMO_* / QF_LIVE_* credentials in local.env — never invents success.
# Usage: .\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker exness -Slot demo-a

param(
  [Parameter(Mandatory = $true)]
  [ValidateSet("weltrade", "xm", "exness", "hfm", "justmarkets", "ic-markets", "pepperstone", "fp-markets")]
  [string]$Broker,
  [string]$Slot = "demo-a",
  [ValidateSet("demo", "live")]
  [string]$Env = "demo",
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

Write-Host "Verifying broker=$Broker env=$Env slot=$Slot (passwords never printed)"

function Invoke-WorkerPython {
  param([Parameter(Mandatory = $true)][string[]]$ModuleArgs)
  # Python logging to stderr must not trip $ErrorActionPreference=Stop.
  $prevEap = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $venvPy = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) {
      & $venvPy @ModuleArgs 2>&1 | ForEach-Object { "$_" }
      return $LASTEXITCODE
    }
    if (Get-Command poetry -ErrorAction SilentlyContinue) {
      & poetry run python @ModuleArgs 2>&1 | ForEach-Object { "$_" }
      return $LASTEXITCODE
    }
    & python @ModuleArgs 2>&1 | ForEach-Object { "$_" }
    return $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $prevEap
  }
}

$null = Invoke-WorkerPython -ModuleArgs @("-m", "services.mt5_worker_agent.main", "capacity")
$code = Invoke-WorkerPython -ModuleArgs @(
  "-m", "services.mt5_worker_agent.main", "verify-broker",
  "--broker", $Broker, "--slot", $Slot, "--env", $Env
)
if ($AlsoRejectTest) {
  Write-Host "Running invalid-credential rejection test"
  $code = Invoke-WorkerPython -ModuleArgs @(
    "-m", "services.mt5_worker_agent.main", "reject-demo",
    "--broker", $Broker, "--slot", $Slot, "--env", $Env
  )
}
if ($null -eq $code) { $code = 1 }
exit $code
