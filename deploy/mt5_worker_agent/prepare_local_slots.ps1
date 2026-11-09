# Prepare isolated portable MT5 copies for demo slots on this Windows machine.
# Copies from Program Files MetaTrader 5 — does not modify the LIVE process.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$free = (Get-PSDrive C).Free
Write-Host ("Disk free bytes on C: {0:N0} ({1:N2} GB)" -f $free, ($free/1GB))
if ($free -lt 2GB) {
  Write-Host "ERROR: Need at least ~2GB free to prepare 3 portable slots safely."
  exit 2
}

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

poetry run python -m services.mt5_worker_agent.main prepare-slots @args
poetry run python -m services.mt5_worker_agent.main status
