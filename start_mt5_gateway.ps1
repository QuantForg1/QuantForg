# Convenience launcher at repo root - delegates to deploy/mt5_gateway/start_gateway.ps1
$ErrorActionPreference = "Stop"
& "$PSScriptRoot\deploy\mt5_gateway\start_gateway.ps1"
