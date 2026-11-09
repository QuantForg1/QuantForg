# Start local multi-slot supervisor on the EXISTING Windows machine.
# Does NOT kill or reconfigure the LIVE Program Files terminal.
# Does NOT enable LIVE multi-user order submit.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$envFile = Join-Path $PSScriptRoot "local.env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $pair = $_.Split('=', 2)
    if ($pair.Length -eq 2) {
      $name = $pair[0].Trim()
      $val = $pair[1].Trim().Trim('"').Trim("'")
      Set-Item -Path "Env:$name" -Value $val
    }
  }
  Write-Host "Loaded local.env (values not printed)."
} else {
  Write-Host "WARN: local.env not found — copy local.env.example first."
}

Write-Host "QuantForg local MT5 worker supervisor"
Write-Host "LIVE terminal override = $env:QF_ALLOW_WORKER_ON_LIVE_TERMINAL (must be false)"
poetry run python -m services.mt5_worker_agent.main supervise
