# Idempotent Windows VPS deployment entrypoint for QuantForg MT5 + Gateway.
# Safe to run multiple times. Does not place trades. Does not print secrets.
# Does NOT git-pull unless -GitPull is passed.
#
# Run ON the Windows VPS from an elevated PowerShell:
#   cd C:\QuantForg
#   powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\deploy_production_vps.ps1
#
# Optional:
#   -SkipInstallTask   configure only; do not register/start tasks
#   -GitPull           fetch+pull origin/main before verifying
#   -InstallDeps       poetry install into .venv

param(
  [string]$RepoRoot = "",
  [string]$TerminalPath = "C:\Program Files\MetaTrader 5\terminal64.exe",
  [switch]$SkipInstallTask,
  [switch]$GitPull,
  [switch]$InstallDeps
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml"))) {
  throw "pyproject.toml not found. Pass -RepoRoot to the QuantForg clone."
}
Set-Location $RepoRoot

$ReportDir = Join-Path $RepoRoot "docs\production\reports\gateway_supervisor"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$Report = Join-Path $ReportDir "deploy_production_vps_report.txt"

function Write-Step([string]$msg) {
  $line = "[{0}] {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $msg
  Add-Content -Path $Report -Value $line -Encoding UTF8
  Write-Host $line
}

"" | Set-Content -Path $Report -Encoding UTF8
Write-Step "begin deploy_production_vps"
Write-Step ("repo={0}" -f $RepoRoot)

$os = [System.Environment]::OSVersion.VersionString
if ($os -notmatch "Windows") { throw "Windows required: $os" }
Write-Step ("windows={0}" -f $os)

$py = (& py -3.13 --version 2>$null | Out-String).Trim()
if ($py -notmatch "3\.13") { throw "Python 3.13 required via py -3.13" }
Write-Step ("python={0}" -f $py)

try {
  $poetry = (& py -3.13 -m poetry --version 2>$null | Out-String).Trim()
  Write-Step ("poetry={0}" -f $poetry)
} catch {
  Write-Step "poetry missing (WARN) - .venv may still be valid"
}

$venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  throw "Missing $venvPy. Create it with: py -3.13 -m poetry install"
}
$venvVer = & $venvPy -c "import sys; print(sys.version.split()[0])"
if ("$venvVer" -notmatch "^3\.13") {
  throw "venv is not Python 3.13: $venvVer"
}
Write-Step ("venv={0}" -f $venvVer)

if ($GitPull) {
  Write-Step "git pull origin main"
  git fetch origin main
  git checkout main
  git pull origin main
}
$sha = (git rev-parse HEAD).Trim()
Write-Step ("git_sha={0}" -f $sha)

if ($InstallDeps) {
  Write-Step "poetry install"
  & py -3.13 -m poetry install --no-interaction
}

& $venvPy -c "import uvicorn, fastapi; import services.mt5_gateway"
if ($LASTEXITCODE -ne 0) { throw "Gateway package import failed in .venv" }
& $venvPy -c "import MetaTrader5"
if ($LASTEXITCODE -ne 0) {
  throw "MetaTrader5 package missing in .venv. On the VPS: py -3.13 -m poetry run pip install MetaTrader5"
}
Write-Step "dependencies ok"

if (-not (Test-Path -LiteralPath $TerminalPath)) {
  throw "MT5 executable not found: $TerminalPath"
}
Write-Step ("mt5_executable={0}" -f $TerminalPath)

$required = @(
  "deploy\mt5_gateway\supervise_gateway.ps1",
  "deploy\mt5_gateway\start_gateway.ps1",
  "deploy\mt5_gateway\install_gateway_task.ps1",
  "deploy\mt5_gateway\start_mt5_terminal.ps1",
  "deploy\mt5_gateway\install_mt5_terminal_task.ps1",
  "deploy\mt5_gateway\verify_production_vps.ps1"
)
foreach ($rel in $required) {
  $p = Join-Path $RepoRoot $rel
  if (-not (Test-Path $p)) { throw "Missing $p" }
}
Write-Step "gateway scripts present"

$envExample = Join-Path $RepoRoot "deploy\mt5_gateway\gateway.env.example"
$dotenv = Join-Path $RepoRoot ".env"
if (-not (Test-Path $dotenv)) {
  Write-Step "WARN: repo .env not found. Copy gateway.env.example values locally; do not commit secrets."
  Write-Step ("example={0}" -f $envExample)
} else {
  Write-Step ".env present (values not printed)"
}

Write-Step "starting MT5 if needed (duplicate start prevented)"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "deploy\mt5_gateway\start_mt5_terminal.ps1") -TerminalPath $TerminalPath

if (-not $SkipInstallTask) {
  Write-Step "install QuantForgMT5Terminal (idempotent)"
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "deploy\mt5_gateway\install_mt5_terminal_task.ps1") -SkipStart
  Write-Step "install QuantForgMT5Gateway (idempotent)"
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "deploy\mt5_gateway\install_gateway_task.ps1") -SkipStart
  Write-Step "start scheduled tasks"
  Start-ScheduledTask -TaskName "QuantForgMT5Terminal" -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 5
  Start-ScheduledTask -TaskName "QuantForgMT5Gateway" -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 8
} else {
  Write-Step "SkipInstallTask set - tasks not registered"
}

Write-Step "running verify_production_vps.ps1"
$verify = Join-Path $RepoRoot "deploy\mt5_gateway\verify_production_vps.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $verify -RepoRoot $RepoRoot
$verifyCode = $LASTEXITCODE

Write-Step ("verify_exit={0}" -f $verifyCode)
Write-Step "end deploy_production_vps"
Write-Host ""
Write-Host "Deployment report: $Report"
Write-Host "This script does not configure Railway, Cloudflare, or auto-logon."
Write-Host "It does not claim production health on any other host."
if ($verifyCode -ne 0) { exit $verifyCode }
exit 0
