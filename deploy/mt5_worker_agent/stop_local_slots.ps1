# Stop only portable worker slot terminals. Never targets Program Files LIVE.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$envFile = Join-Path $PSScriptRoot "local.env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $pair = $_.Split('=', 2)
    if ($pair.Length -eq 2) {
      Set-Item -Path ("Env:" + $pair[0].Trim()) -Value ($pair[1].Trim().Trim('"').Trim("'"))
    }
  }
}

poetry run python -m services.mt5_worker_agent.main stop-slots
poetry run python -m services.mt5_worker_agent.main status
