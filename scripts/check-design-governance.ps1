# Ensures Design Bible / governance docs remain present (ADR-0022).
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Required = @(
  "docs/design/README.md",
  "docs/design/product-governance.md",
  "docs/design/feature-lifecycle.md",
  "docs/design/ux-principles.md",
  "docs/design/design-tokens.md",
  "docs/design/typography.md",
  "docs/design/accessibility.md",
  "docs/design/performance-budgets.md",
  "docs/design/component-acceptance-checklist.md",
  "docs/design/feature-acceptance-checklist.md",
  "docs/adr/0022-design-bible-and-product-governance.md"
)

$missing = $false
foreach ($rel in $Required) {
  $path = Join-Path $Root $rel
  if (-not (Test-Path -LiteralPath $path)) {
    Write-Host "MISSING: $rel"
    $missing = $true
  }
}

if ($missing) {
  Write-Host "Design governance docs missing. See docs/design/README.md (ADR-0022)."
  exit 1
}

Write-Host "Design governance docs OK ($($Required.Count) files)."
