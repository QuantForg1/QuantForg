# Deploy reconnect-loop fix on Windows host and start a fresh post-fix soak.
# Run elevated on the production Windows machine only.
# Does NOT declare PAT/OAT ACCEPTED.

$ErrorActionPreference = "Stop"
$RepoRoot = "C:\Users\P7 PROVIDER\QuantForg"
$Branch = "cursor/v7-1-acceptance-evidence"
$ReportDir = Join-Path $RepoRoot "docs\production\reports\oat_v71"
$Python = "C:\Python314\python.exe"
$Log = Join-Path $ReportDir "post_fix_deploy.log"
$DeployJson = Join-Path $ReportDir "post_fix_deploy.json"
$SoakOut = Join-Path $ReportDir "soak_24h_metrics.jsonl"
$SoakLatest = Join-Path $ReportDir "soak_24h_latest.json"
$SoakMeta = Join-Path $ReportDir "post_fix_soak_start.json"

function Write-Log([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $msg
  Add-Content -Path $Log -Value $line
  Write-Host $line
}

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
"" | Set-Content $Log
Write-Log "begin deploy+soak"

Set-Location $RepoRoot
Write-Log "git fetch/checkout/pull $Branch"
git fetch origin $Branch
git checkout $Branch
git pull origin $Branch
$Commit = (git rev-parse HEAD).Trim()
Write-Log "HEAD=$Commit"

# Stop listener on 8765
$pids = @()
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { $pids += $_.OwningProcess }
$pids = $pids | Select-Object -Unique
foreach ($procId in $pids) {
  Write-Log "killing gateway pid=$procId"
  taskkill /F /PID $procId 2>&1 | Out-String | ForEach-Object { Write-Log $_ }
}
Start-Sleep -Seconds 4

# Archive prior soak (pre-fix evidence) then start clean metrics file
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
if (Test-Path $SoakOut) {
  $archive = Join-Path $ReportDir ("soak_24h_metrics_pre_fix_archive_{0}.jsonl" -f $stamp)
  Move-Item -Force $SoakOut $archive
  Write-Log "archived previous soak -> $archive"
}
New-Item -ItemType File -Force -Path $SoakOut | Out-Null

Write-Log "starting gateway"
$outLog = Join-Path $ReportDir "gateway_post_fix.out.log"
$errLog = Join-Path $ReportDir "gateway_post_fix.err.log"
$gatewayArgs = @("-m", "services.mt5_gateway.main")
Start-Process -FilePath $Python -ArgumentList $gatewayArgs -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog
Start-Sleep -Seconds 8

$health = $null
try {
  $health = Invoke-RestMethod "http://127.0.0.1:8765/health" -TimeoutSec 10
  Write-Log ("health gateway_version={0} connected={1}" -f $health.gateway_version, $health.mt5.connected)
} catch {
  Write-Log ("health failed: {0}" -f $_.Exception.Message)
  throw
}

$deployAt = (Get-Date).ToUniversalTime().ToString("o")
@{
  deployed_at = $deployAt
  branch = $Branch
  commit = $Commit
  gateway_version = $health.gateway_version
  mt5_connected = [bool]$health.mt5.connected
  session_mode = $health.mt5.session_mode
  server = $health.mt5.server
  note = "Reconnect-loop fix deployed. PAT/OAT NOT ACCEPTED."
} | ConvertTo-Json -Depth 6 | Set-Content $DeployJson

# Start fresh 24h soak in background
$soakStart = (Get-Date).ToUniversalTime().ToString("o")
@{
  soak_started_at = $soakStart
  commit = $Commit
  gateway_version = $health.gateway_version
  metrics_path = $SoakOut
  script = "docs/production/reports/oat_v71/soak_24h.ps1"
  post_fix = $true
  pat_oat_accepted = $false
} | ConvertTo-Json -Depth 6 | Set-Content $SoakMeta

Write-Log "starting soak_24h.ps1"
$soakScript = Join-Path $ReportDir "soak_24h.ps1"
$soakArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $soakScript)
Start-Process -FilePath "powershell.exe" -ArgumentList $soakArgs -WorkingDirectory $RepoRoot -WindowStyle Hidden

Write-Log ("soak started at {0}" -f $soakStart)
Write-Log "done - PAT/OAT remain NOT ACCEPTED until post-fix soak completes"
Write-Host "Deploy JSON: $DeployJson"
Write-Host "Soak start JSON: $SoakMeta"
