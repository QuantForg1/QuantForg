# Safe temporary artifact cleanup for disk pressure on the local Windows host.
# Does NOT touch:
#   - C:\Program Files\MetaTrader 5 (LIVE)
#   - C:\QuantForg-Workspace\mt5_worker_slots (portable worker data)
#   - user documents / broker credentials

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Show-Free {
  $free = (Get-PSDrive C).Free
  Write-Host ("C: free = {0:N2} GB" -f ($free / 1GB))
}

Show-Free
$targets = @(
  (Join-Path $Root "frontend\.next"),
  (Join-Path $Root "frontend\node_modules\.cache"),
  (Join-Path $Root ".pytest_cache"),
  (Join-Path $Root "frontend\.turbo")
)
foreach ($t in $targets) {
  if (Test-Path $t) {
    Write-Host "Removing $t"
    Remove-Item -Recurse -Force $t -ErrorAction SilentlyContinue
  }
}
Show-Free
Write-Host "LIVE MT5 and mt5_worker_slots were not modified."
