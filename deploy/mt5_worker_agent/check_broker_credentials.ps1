# Report which broker Demo/Live credential env keys are missing.
# Never prints secret values. Loads deploy/mt5_worker_agent/local.env if present.
# Usage: .\deploy\mt5_worker_agent\check_broker_credentials.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $Root "pyproject.toml"))) {
  $Root = (Get-Location).Path
}
Set-Location $Root

$EnvFile = Join-Path $PSScriptRoot "local.env"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    if ($_ -match '^([^=]+)=(.*)$') {
      Set-Item -Path "Env:$($Matches[1].Trim())" -Value $Matches[2].Trim()
    }
  }
  Write-Host "Loaded local.env (values not printed)"
} else {
  Write-Host "No local.env found — reporting against process environment only"
}

poetry run python -c @"
import json
from services.mt5_worker_agent.broker_demo_adapters import (
    missing_credential_keys,
    resolve_credentials,
)

SLUGS = ['weltrade','exness','hfm','ic-markets','pepperstone','fp-markets','xm']
rows = []
for slug in SLUGS:
    for env in ('demo','live'):
        missing = missing_credential_keys(slug, environment=env)
        creds = resolve_credentials(slug, environment=env)
        rows.append({
            'broker': slug,
            'env': env,
            'status': 'READY_TO_VERIFY' if creds is not None else 'BLOCKED_MISSING_CREDENTIALS',
            'login_set': bool(getattr(creds, 'login', None)) if creds else False,
            'server_set': bool(getattr(creds, 'server', None)) if creds else False,
            'missing_keys': missing,
        })
blocked = sum(1 for r in rows if r['status'] != 'READY_TO_VERIFY')
print(json.dumps({'ok': True, 'blocked': blocked, 'rows': rows}, indent=2))
raise SystemExit(1 if blocked else 0)
"@
exit $LASTEXITCODE
