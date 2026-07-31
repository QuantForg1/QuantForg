# QuantForg — P0 Gateway Recovery (Windows VPS only)
# Elevated PowerShell. Cloud agents cannot execute this against the VPS.
# Follows docs/production/infra_recovery_evidence/WINDOWS_GATEWAY_RECOVERY.md
#
# Success criteria:
#   http://127.0.0.1:8765/health  -> 200
#   https://gateway.quantforg.com/health -> 200 (no Cloudflare 502)
#   /account: connected, trade_allowed, broker/server, login, account_mode
#
# Compatible with Windows PowerShell 5.1 (ASCII-only).

$ErrorActionPreference = "Stop"
$RepoRoot = "C:\Users\P7 PROVIDER\QuantForg"
$ReportDir = Join-Path $RepoRoot "docs\production\reports\oat_v71"
$Log = Join-Path $ReportDir "p0_gateway_recovery.log"
$EvidenceJson = Join-Path $ReportDir "p0_gateway_recovery_verify.json"

function Write-Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $msg
  Add-Content -Path $Log -Value $line
  Write-Host $line
}

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
"" | Set-Content -Path $Log
Write-Log "begin p0_gateway_recovery"

Set-Location $RepoRoot

# 1) Core gateway restart + session attach (existing proven script)
$deploy = Join-Path $RepoRoot "deploy\mt5_gateway\deploy_main_gateway.ps1"
if (-not (Test-Path $deploy)) {
  throw "missing deploy_main_gateway.ps1"
}
Write-Log "invoking deploy_main_gateway.ps1"
& $deploy
Write-Log "deploy_main_gateway.ps1 completed"

# 2) Cloudflare tunnel / service checks (best-effort)
$tunnelHints = @()
try {
  $svc = Get-Service -Name "cloudflared" -ErrorAction SilentlyContinue
  if ($null -ne $svc) {
    $tunnelHints += ("cloudflared_service_status={0}" -f $svc.Status)
    if ($svc.Status -ne "Running") {
      Write-Log "starting cloudflared service"
      Start-Service -Name "cloudflared"
      Start-Sleep -Seconds 5
      $svc = Get-Service -Name "cloudflared"
      $tunnelHints += ("cloudflared_service_status_after={0}" -f $svc.Status)
    }
  } else {
    $tunnelHints += "cloudflared_service=not_installed_as_windows_service"
  }
} catch {
  $tunnelHints += ("cloudflared_check_error={0}" -f $_.Exception.Message)
}

try {
  $nssm = Get-Service -Name "QuantForgMT5Gateway" -ErrorAction SilentlyContinue
  if ($null -ne $nssm) {
    $tunnelHints += ("QuantForgMT5Gateway={0}" -f $nssm.Status)
  } else {
    $tunnelHints += "QuantForgMT5Gateway=not_installed"
  }
} catch {
  $tunnelHints += ("nssm_check_error={0}" -f $_.Exception.Message)
}

# 3) Local + public verify
$tokenLine = Get-Content -Path ".env" |
  Where-Object { $_ -match '^\s*MT5_GATEWAY_TOKEN\s*=' } |
  Select-Object -Last 1
if (-not $tokenLine) { throw "MT5_GATEWAY_TOKEN missing from .env" }
$token = (($tokenLine -split "=", 2)[1]).Trim().Trim('"').Trim("'")
$authHeaders = @{ Authorization = ("Bearer {0}" -f $token) }

$localHealth = Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -TimeoutSec 15
$localAccount = Invoke-RestMethod -Uri "http://127.0.0.1:8765/account" -Headers $authHeaders -TimeoutSec 15

$publicHealthStatus = $null
$publicBody = $null
try {
  $resp = Invoke-WebRequest -Uri "https://gateway.quantforg.com/health" -TimeoutSec 20 -UseBasicParsing
  $publicHealthStatus = [int]$resp.StatusCode
  $publicBody = $resp.Content
} catch {
  if ($_.Exception.Response) {
    $publicHealthStatus = [int]$_.Exception.Response.StatusCode.value__
  }
  $publicBody = ("{0}" -f $_.Exception.Message)
}

$mt5Connected = $false
$mt5Server = $null
if ($null -ne $localHealth.mt5) {
  $mt5Connected = [bool]$localHealth.mt5.connected
  $mt5Server = $localHealth.mt5.server
}

$payload = [ordered]@{
  recovered_at = (Get-Date).ToUniversalTime().ToString("o")
  local_health_ok = $true
  public_health_http_status = $publicHealthStatus
  public_health_http_200 = ($publicHealthStatus -eq 200)
  mt5_connected = $mt5Connected
  trade_allowed = [bool]$localAccount.trade_allowed
  broker_or_server = $mt5Server
  account_login = $localAccount.login
  account_mode = $localAccount.account_mode
  gateway_version = $localHealth.gateway_version
  bridge_available = $localHealth.bridge_available
  tunnel_hints = $tunnelHints
  public_body_snippet = (("{0}" -f $publicBody).Substring(0, [Math]::Min(200, ("{0}" -f $publicBody).Length)))
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -Path $EvidenceJson -Encoding UTF8
Write-Log ("evidence -> {0}" -f $EvidenceJson)

if (-not $payload.public_health_http_200) {
  throw ("public /health not 200 (got {0}) - restart cloudflared / tunnel and re-run" -f $publicHealthStatus)
}
if (-not $payload.mt5_connected) { throw "mt5 not connected" }
if (-not $payload.trade_allowed) { throw "trade_allowed=false" }
if (-not $payload.broker_or_server) { throw "broker/server missing" }
if (-not $payload.account_login) { throw "account login missing" }

Write-Log "SUCCESS p0_gateway_recovery"
$payload | ConvertTo-Json -Depth 6
