# Validate QF_DEMO_* local.env presence without printing secret values.
# Usage (from repo root):
#   .\scripts\validate_demo_local_env.ps1
#   .\scripts\validate_demo_local_env.ps1 -Broker exness
#
# Never commits credentials. Never writes passwords to stdout.

param(
  [string]$Broker = "",
  [string]$EnvFile = "deploy/mt5_worker_agent/local.env"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$path = Join-Path $root $EnvFile

if (-not (Test-Path -LiteralPath $path)) {
  Write-Host "MISSING: $EnvFile (copy from local.env.example; do not commit)"
  exit 2
}

$map = @{}
Get-Content -LiteralPath $path | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
  $idx = $line.IndexOf("=")
  $k = $line.Substring(0, $idx).Trim()
  $v = $line.Substring($idx + 1).Trim()
  $map[$k] = $v
}

function HasVal([string]$key) {
  return $map.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace([string]$map[$key])
}

Write-Host "local.env present"
Write-Host ("QF_ALLOW_WORKER_ON_LIVE_TERMINAL=" + ($(if (HasVal "QF_ALLOW_WORKER_ON_LIVE_TERMINAL") { $map["QF_ALLOW_WORKER_ON_LIVE_TERMINAL"] } else { "(unset)" })))
Write-Host ("QUANTFORG_API_BASE_URL set=" + (HasVal "QUANTFORG_API_BASE_URL"))
Write-Host ("WORKER_SERVICE_TOKEN set=" + (HasVal "WORKER_SERVICE_TOKEN"))

$brokers = @("EXNESS", "HFM", "IC_MARKETS", "PEPPERSTONE", "FP_MARKETS", "XM")
if ($Broker) {
  $brokers = @($Broker.ToUpper().Replace("-", "_").Replace(" ", "_"))
}

$ready = 0
foreach ($b in $brokers) {
  $login = "QF_DEMO_${b}_LOGIN"
  $pass = "QF_DEMO_${b}_PASSWORD"
  $server = "QF_DEMO_${b}_SERVER"
  $ok = (HasVal $login) -and (HasVal $pass) -and (HasVal $server)
  if ($ok) {
    $ready++
    Write-Host "READY_KEYS: $b (login/password/server present; values not printed)"
  } else {
    Write-Host "MISSING_KEYS: $b ($login / $pass / $server)"
  }
}

if ((HasVal "QF_ALLOW_WORKER_ON_LIVE_TERMINAL") -and $map["QF_ALLOW_WORKER_ON_LIVE_TERMINAL"] -eq "true") {
  Write-Host "FAIL: QF_ALLOW_WORKER_ON_LIVE_TERMINAL must stay false"
  exit 1
}

Write-Host "Brokers with complete QF_DEMO_* key triples: $ready / $($brokers.Count)"
if ($ready -eq 0) {
  Write-Host "Owner action: fill disposable DEMO credentials into local.env via secure delivery, then re-run verify_demo_broker.ps1"
  exit 3
}
exit 0
