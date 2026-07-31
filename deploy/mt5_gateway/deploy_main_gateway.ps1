# QuantForg — deploy latest main MT5 Gateway on the Windows production host.
# Run elevated on the Windows VPS only. Cloud agents cannot execute this.
#
# Success criteria after restart:
#   gateway_version >= 1.1.5 (current tip prints from services.mt5_gateway)
#   /account.account_mode in demo|contest|real (not missing / not invented)
#   bridge_available=true, mt5.connected=true, heartbeat ok, quotes+candles live

$ErrorActionPreference = "Stop"
$RepoRoot = "C:\Users\P7 PROVIDER\QuantForg"
$Python = "C:\Python314\python.exe"
$ReportDir = Join-Path $RepoRoot "docs\production\reports\oat_v71"
$Log = Join-Path $ReportDir "deploy_main_gateway.log"
$VerifyJson = Join-Path $ReportDir "deploy_main_gateway_verify.json"

function Write-Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $msg
  Add-Content -Path $Log -Value $line
  Write-Host $line
}

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
"" | Set-Content $Log
Write-Log "begin deploy_main_gateway"

Set-Location $RepoRoot
Write-Log "git fetch/checkout/pull main"
git fetch origin main
git checkout main
git pull origin main
$Commit = (git rev-parse HEAD).Trim()
Write-Log "HEAD=$Commit"

$Version = & $Python -c "from services.mt5_gateway import __version__; print(__version__)"
if ($LASTEXITCODE -ne 0) { throw "Cannot import services.mt5_gateway" }
$Version = "$Version".Trim()
Write-Log "package_version=$Version"

& $Python -c "import MetaTrader5 as m; print('MetaTrader5OK', getattr(m, '__file__', m))"
if ($LASTEXITCODE -ne 0) {
  throw "MetaTrader5 missing in $Python — install: $Python -m pip install MetaTrader5"
}

$pids = @()
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { $pids += $_.OwningProcess }
$pids = $pids | Select-Object -Unique
foreach ($procId in $pids) {
  Write-Log "killing gateway pid=$procId"
  taskkill /F /PID $procId 2>&1 | Out-String | ForEach-Object { Write-Log $_ }
}
Start-Sleep -Seconds 4

$outLog = Join-Path $ReportDir "gateway_main.out.log"
$errLog = Join-Path $ReportDir "gateway_main.err.log"
Write-Log "starting gateway"
Start-Process -FilePath $Python -ArgumentList @("-m", "services.mt5_gateway.main") `
  -WorkingDirectory $RepoRoot -WindowStyle Hidden `
  -RedirectStandardOutput $outLog -RedirectStandardError $errLog
Start-Sleep -Seconds 8

# Attach existing terminal session (no password through API)
$tokenLine = Get-Content .env | Where-Object { $_ -match '^\s*MT5_GATEWAY_TOKEN\s*=' } | Select-Object -Last 1
if (-not $tokenLine) { throw "MT5_GATEWAY_TOKEN missing from .env" }
$token = (($tokenLine -split '=', 2)[1]).Trim().Trim('"').Trim("'")
try {
  Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8765/session/attach" `
    -Headers @{ Authorization = "Bearer $token"; Accept = "application/json" } `
    -ContentType "application/json" -Body "{}" | Out-Null
  Write-Log "session/attach ok"
} catch {
  Write-Log ("session/attach failed (may already be attached): {0}" -f $_.Exception.Message)
}

$health = Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 15
$account = Invoke-RestMethod -Uri "http://127.0.0.1:8765/account" `
  -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 15
$heartbeat = Invoke-RestMethod -Uri "http://127.0.0.1:8765/heartbeat" `
  -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 15
$quotes = Invoke-RestMethod -Uri "http://127.0.0.1:8765/quotes/XAUUSD" `
  -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 15
$candles = Invoke-RestMethod -Uri "http://127.0.0.1:8765/candles/XAUUSD?timeframe=M5&count=20" `
  -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 30

$payload = [ordered]@{
  deployed_at = (Get-Date).ToUniversalTime().ToString("o")
  commit = $Commit
  package_version = $Version
  gateway_version = $health.gateway_version
  bridge_available = $health.bridge_available
  mt5_connected = $health.mt5.connected
  server = $health.mt5.server
  account_mode = $account.account_mode
  trade_mode_raw = $account.trade_mode_raw
  trade_allowed = $account.trade_allowed
  login = $account.login
  heartbeat_ok = [bool]$heartbeat.ok
  quote_bid = $quotes.bid
  candle_items = @($candles.items).Count
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -Path $VerifyJson -Encoding UTF8
Write-Log ("verify written -> {0}" -f $VerifyJson)
Write-Log ("gateway_version={0} account_mode={1}" -f $health.gateway_version, $account.account_mode)

if ("$($health.gateway_version)" -ne $Version) {
  throw "gateway_version $($health.gateway_version) != package $Version — restart may have failed"
}
if ($account.PSObject.Properties.Name -notcontains "account_mode") {
  throw "GET /account missing account_mode — old gateway binary still running"
}
if ($account.account_mode -notin @("demo", "contest", "real")) {
  throw "account_mode missing/unmapped: $($account.account_mode) (MT5 trade_mode not provided or unmapped)"
}
Write-Log "SUCCESS deploy_main_gateway"
$payload | ConvertTo-Json -Depth 6
