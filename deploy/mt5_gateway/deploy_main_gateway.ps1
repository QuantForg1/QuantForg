# QuantForg - deploy latest main MT5 Gateway on the Windows production host.
# Run elevated on the Windows VPS only. Cloud agents cannot execute this.
#
# Success criteria after restart:
#   gateway_version matches services.mt5_gateway.__version__
#   /account.account_mode in demo|contest|real (not missing / not invented)
#   bridge_available=true, mt5.connected=true, heartbeat ok, quotes+candles live
#
# Compatible with Windows PowerShell 5.1 (ASCII-only source; no UTF-8 em-dashes).

$ErrorActionPreference = "Stop"
$RepoRoot = "C:\Users\P7 PROVIDER\QuantForg"
# QuantForg requires Python 3.13 + Poetry project venv (.venv). Never use global Python 3.14.
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  throw "Missing project venv at $Python. Run from repo root: py -3.13 -m poetry install"
}
$ReportDir = Join-Path $RepoRoot "docs\production\reports\oat_v71"
$Log = Join-Path $ReportDir "deploy_main_gateway.log"
$VerifyJson = Join-Path $ReportDir "deploy_main_gateway_verify.json"

function Write-Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $msg
  Add-Content -Path $Log -Value $line
  Write-Host $line
}

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
"" | Set-Content -Path $Log
Write-Log "begin deploy_main_gateway"

Set-Location $RepoRoot
Write-Log "git fetch/checkout/pull main"
git fetch origin main
git checkout main
git pull origin main
$Commit = (git rev-parse HEAD).Trim()
Write-Log ("HEAD={0}" -f $Commit)

$Version = & $Python -c "from services.mt5_gateway import __version__; print(__version__)"
if ($LASTEXITCODE -ne 0) {
  throw "Cannot import services.mt5_gateway"
}
$Version = ("{0}" -f $Version).Trim()
Write-Log ("package_version={0}" -f $Version)

& $Python -c "import MetaTrader5 as m; print('MetaTrader5OK', getattr(m, '__file__', m))"
if ($LASTEXITCODE -ne 0) {
  $hint = "MetaTrader5 missing in project venv ({0}). Install into Poetry env only: py -3.13 -m poetry run pip install MetaTrader5" -f $Python
  throw $hint
}

$pids = @()
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { $pids += $_.OwningProcess }
$pids = $pids | Select-Object -Unique
foreach ($procId in $pids) {
  Write-Log ("killing gateway pid={0}" -f $procId)
  taskkill /F /PID $procId 2>&1 | Out-String | ForEach-Object { Write-Log $_ }
}
Start-Sleep -Seconds 4

$outLog = Join-Path $ReportDir "gateway_main.out.log"
$errLog = Join-Path $ReportDir "gateway_main.err.log"
Write-Log "starting gateway via supervise_gateway.ps1 -Once (Hidden child survives shell close)"
$supervise = Join-Path $RepoRoot "deploy\mt5_gateway\supervise_gateway.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $supervise -Once
if ($LASTEXITCODE -ne 0) {
  throw "supervise_gateway.ps1 -Once failed"
}
Start-Sleep -Seconds 3

# Attach existing terminal session (no password through API)
$tokenLine = Get-Content -Path ".env" |
  Where-Object { $_ -match '^\s*MT5_GATEWAY_TOKEN\s*=' } |
  Select-Object -Last 1
if (-not $tokenLine) {
  throw "MT5_GATEWAY_TOKEN missing from .env"
}
$token = (($tokenLine -split "=", 2)[1]).Trim().Trim('"').Trim("'")

$attachUri = "http://127.0.0.1:8765/session/attach"
$healthUri = "http://127.0.0.1:8765/health"
$accountUri = "http://127.0.0.1:8765/account"
$heartbeatUri = "http://127.0.0.1:8765/heartbeat"
$quotesUri = "http://127.0.0.1:8765/quotes/XAUUSD_I"
# Query string uses single-quoted literal so '&' is never a call operator.
$candlesUri = 'http://127.0.0.1:8765/candles/XAUUSD_I?timeframe=H1&count=200'

try {
  $attachHeaders = @{
    Authorization = ("Bearer {0}" -f $token)
    Accept = "application/json"
  }
  Invoke-RestMethod -Method POST -Uri $attachUri `
    -Headers $attachHeaders `
    -ContentType "application/json" -Body "{}" | Out-Null
  Write-Log "session/attach ok"
} catch {
  Write-Log ("session/attach failed (may already be attached): {0}" -f $_.Exception.Message)
}

$authHeaders = @{
  Authorization = ("Bearer {0}" -f $token)
}

$health = Invoke-RestMethod -Uri $healthUri -TimeoutSec 15
$account = Invoke-RestMethod -Uri $accountUri -Headers $authHeaders -TimeoutSec 15
$heartbeat = Invoke-RestMethod -Uri $heartbeatUri -Headers $authHeaders -TimeoutSec 15
$quotes = Invoke-RestMethod -Uri $quotesUri -Headers $authHeaders -TimeoutSec 15
$candles = Invoke-RestMethod -Uri $candlesUri -Headers $authHeaders -TimeoutSec 30

$mt5Connected = $false
$mt5Server = $null
if ($null -ne $health.mt5) {
  $mt5Connected = [bool]$health.mt5.connected
  $mt5Server = $health.mt5.server
}

$candleCount = 0
if ($null -ne $candles.items) {
  $candleCount = @($candles.items).Count
}

$payload = [ordered]@{
  deployed_at = (Get-Date).ToUniversalTime().ToString("o")
  commit = $Commit
  package_version = $Version
  gateway_version = $health.gateway_version
  bridge_available = $health.bridge_available
  mt5_connected = $mt5Connected
  server = $mt5Server
  account_mode = $account.account_mode
  trade_mode_raw = $account.trade_mode_raw
  trade_allowed = $account.trade_allowed
  login = $account.login
  heartbeat_ok = [bool]$heartbeat.ok
  quote_bid = $quotes.bid
  candle_items = $candleCount
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -Path $VerifyJson -Encoding UTF8
Write-Log ("verify written -> {0}" -f $VerifyJson)
Write-Log ("gateway_version={0} account_mode={1}" -f $health.gateway_version, $account.account_mode)

if (("{0}" -f $health.gateway_version) -ne $Version) {
  throw ("gateway_version {0} != package {1} - restart may have failed" -f $health.gateway_version, $Version)
}

$propNames = @($account.PSObject.Properties | ForEach-Object { $_.Name })
if ($propNames -notcontains "account_mode") {
  throw "GET /account missing account_mode - old gateway binary still running"
}

$allowedModes = @("demo", "contest", "real")
if ($allowedModes -notcontains $account.account_mode) {
  throw ("account_mode missing/unmapped: {0} (MT5 trade_mode not provided or unmapped)" -f $account.account_mode)
}

Write-Log "SUCCESS deploy_main_gateway"
$payload | ConvertTo-Json -Depth 6
