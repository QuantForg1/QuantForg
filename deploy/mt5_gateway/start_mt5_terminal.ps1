# Start MetaTrader 5 terminal if it is not already running.
# Does NOT pass broker login/password, does NOT change trading settings,
# does NOT place orders, does NOT modify positions.
#
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\start_mt5_terminal.ps1
#
# Optional:
#   -TerminalPath "C:\Program Files\MetaTrader 5\terminal64.exe"
#   Env MT5_TERMINAL_PATH overrides the default when -TerminalPath is omitted.

param(
  [string]$TerminalPath = ""
)

$ErrorActionPreference = "Stop"

function Write-Mt5Log([string]$msg) {
  Write-Host ("[{0}] {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $msg)
}

$defaultPath = "C:\Program Files\MetaTrader 5\terminal64.exe"
$envPath = ($env:MT5_TERMINAL_PATH | ForEach-Object { "$_" })
if ([string]::IsNullOrWhiteSpace($TerminalPath)) {
  if (-not [string]::IsNullOrWhiteSpace($envPath)) {
    $TerminalPath = $envPath.Trim()
  } else {
    $TerminalPath = $defaultPath
  }
}

$existing = @(Get-Process -Name "terminal64","terminal" -ErrorAction SilentlyContinue)
if ($existing.Count -gt 0) {
  $ids = ($existing | ForEach-Object { $_.Id }) -join ","
  Write-Mt5Log ("mt5_detected already running pids={0} duplicate start prevented" -f $ids)
  exit 0
}

if (-not (Test-Path -LiteralPath $TerminalPath)) {
  throw "MT5 executable not found: $TerminalPath"
}

Write-Mt5Log ("starting mt5 path={0}" -f $TerminalPath)
# No /login, no /config, no /portable unless the operator already uses that install.
Start-Process -FilePath $TerminalPath
Start-Sleep -Seconds 3
$after = @(Get-Process -Name "terminal64","terminal" -ErrorAction SilentlyContinue)
if ($after.Count -eq 0) {
  throw "terminal64.exe did not remain running after Start-Process"
}
Write-Mt5Log ("mt5_recovered started pid={0}" -f $after[0].Id)
exit 0
