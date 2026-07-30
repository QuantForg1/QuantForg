# Sync Windows soak evidence into git for the cloud PAT/OAT verifier.
# Run on the Windows production host only. Does not invent metrics.

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

$metrics = Join-Path $RepoRoot "docs\production\reports\oat_v71\soak_24h_metrics.jsonl"
$latest = Join-Path $RepoRoot "docs\production\reports\oat_v71\soak_24h_latest.json"

if (-not (Test-Path $metrics)) {
  throw "Missing $metrics — start docs/production/reports/oat_v71/soak_24h.ps1 first."
}
if (-not (Test-Path $latest)) {
  throw "Missing $latest"
}

Write-Host "=== soak_24h_latest.json ==="
Get-Content $latest
Write-Host "=== soak_24h_metrics.jsonl tail ==="
Get-Content $metrics -Tail 5
Write-Host ("Bytes metrics={0} latest={1}" -f (Get-Item $metrics).Length, (Get-Item $latest).Length)

git status --short -- "docs/production/reports/oat_v71/soak_24h_metrics.jsonl" "docs/production/reports/oat_v71/soak_24h_latest.json"
git add -- "docs/production/reports/oat_v71/soak_24h_metrics.jsonl" "docs/production/reports/oat_v71/soak_24h_latest.json"
if (git diff --cached --quiet) {
  Write-Host "No soak file changes to commit (already synced or unchanged)."
  exit 0
}
git commit -m "Import Windows v7.1 soak operational evidence"
Write-Host "Committed. Push with: git push"
