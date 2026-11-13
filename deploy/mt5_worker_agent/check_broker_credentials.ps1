# Report which broker Demo/Live credential env keys are missing.
# Never prints secret values. Loads deploy/mt5_worker_agent/local.env if present.
# Usage: .\deploy\mt5_worker_agent\check_broker_credentials.ps1
#
# Note: do not use `poetry run python -c` with a multiline here-string on Windows —
# Poetry silently no-ops (exit 0, no stdout). Always invoke a module/script instead.

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
  Write-Host "Loaded local.env (values not printed)"
} else {
  Write-Host "No local.env found — reporting against process environment only"
}

$moduleArgs = @(
  "-m",
  "services.mt5_worker_agent.check_broker_credentials"
)

# Prefer an existing venv first (avoids Poetry creating an empty env on fresh worktrees).
# Module form avoids the Windows Poetry multiline `python -c` no-op.
$code = 1
$venvPy = Join-Path $Root ".venv\Scripts\python.exe"
$parentVenvPy = Join-Path (Split-Path -Parent $Root) "QuantForg\.venv\Scripts\python.exe"
if (Test-Path $venvPy) {
  & $venvPy @moduleArgs
  $code = $LASTEXITCODE
} elseif (Test-Path $parentVenvPy) {
  & $parentVenvPy @moduleArgs
  $code = $LASTEXITCODE
} elseif (Get-Command poetry -ErrorAction SilentlyContinue) {
  & poetry run python @moduleArgs
  $code = $LASTEXITCODE
} else {
  & python @moduleArgs
  $code = $LASTEXITCODE
}

if ($null -eq $code) { $code = 1 }
exit $code
