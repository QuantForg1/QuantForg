$end = (Get-Date).AddHours(24)
$out = "C:\Users\P7 PROVIDER\QuantForg\docs\production\reports\oat_v71\soak_24h_metrics.jsonl"
$latest = "C:\Users\P7 PROVIDER\QuantForg\docs\production\reports\oat_v71\soak_24h_latest.json"
while ((Get-Date) -lt $end) {
  $row = [ordered]@{ ts = (Get-Date).ToUniversalTime().ToString("o"); gateway=$null; railway=$null; cpu=$null; ram_mb=$null; err=$null }
  try {
    $t0 = Get-Date
    $h2 = Invoke-RestMethod http://127.0.0.1:8765/health -TimeoutSec 8
    $lat = ((Get-Date) - $t0).TotalMilliseconds
    $row.gateway = @{ ok=$true; connected=$h2.mt5.connected; session=$h2.mt5.session_mode; hb=$h2.mt5.last_heartbeat_at; latency_ms=[math]::Round($lat,2); mt5_latency_ms=$h2.mt5.latency_ms }
  } catch { $row.gateway = @{ ok=$false; error=$_.Exception.Message } }
  try {
    $t0 = Get-Date
    $a = Invoke-RestMethod https://quantforg-production.up.railway.app/api/v1/health -TimeoutSec 15
    $row.railway = @{ ok=$true; status=$a.status; latency_ms=[math]::Round(((Get-Date)-$t0).TotalMilliseconds,2) }
  } catch { $row.railway = @{ ok=$false; error=$_.Exception.Message } }
  try {
    $cpuSample = (Get-Counter '\Processor(_Total)\% Processor Time' -ErrorAction SilentlyContinue).CounterSamples.CookedValue
    $row.cpu = [math]::Round([double]$cpuSample, 2)
    $gwPid = (Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue | Select-Object -First 1).OwningProcess
    $procs = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Id -eq $gwPid -or $_.ProcessName -eq 'terminal64' }
    $ws = ($procs | Measure-Object WorkingSet64 -Sum).Sum
    $row.ram_mb = [math]::Round(($ws/1MB),2)
  } catch { $row.err = $_.Exception.Message }
  ($row | ConvertTo-Json -Compress) | Add-Content $out
  ($row | ConvertTo-Json -Depth 6) | Set-Content $latest
  Start-Sleep -Seconds 60
}
