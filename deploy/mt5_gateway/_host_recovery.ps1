# Shared VPS host recovery helpers (MT5 process, Cloudflared service).
# Dot-source from supervise/watchdog/verify/recover.
# NEVER sends broker orders. NEVER reads or logs tunnel/gateway tokens.

$script:CloudflaredServiceName = "Cloudflared"
$script:PublicLiveUri = "https://gateway.quantforg.com/health/live"

function Test-Mt5TerminalProcess {
  $procs = @(Get-Process -Name "terminal64","terminal" -ErrorAction SilentlyContinue)
  return ($procs.Count -gt 0)
}

function Get-Mt5TerminalPids {
  $procs = @(Get-Process -Name "terminal64","terminal" -ErrorAction SilentlyContinue)
  return @($procs | ForEach-Object { [int]$_.Id })
}

function Get-CloudflaredService {
  return Get-Service -Name $script:CloudflaredServiceName -ErrorAction SilentlyContinue
}

function Test-CloudflaredServiceRunning {
  $svc = Get-CloudflaredService
  if ($null -eq $svc) { return $false }
  return ($svc.Status -eq "Running")
}

function Get-CloudflaredPids {
  $procs = @(Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue)
  return @($procs | ForEach-Object { [int]$_.Id })
}

function Get-HostHealthState {
  param(
    [int]$ListenerCount,
    [bool]$LiveOk,
    [bool]$Mt5Connected,
    [bool]$Mt5Process,
    [bool]$CloudflaredRunning,
    [int]$CloudflaredCount,
    [bool]$PublicLiveOk
  )
  if ($ListenerCount -ne 1 -or -not $LiveOk -or -not $Mt5Process -or -not $CloudflaredRunning) {
    return "CRITICAL"
  }
  if ($ListenerCount -eq 1 -and $LiveOk -and $Mt5Process -and $CloudflaredRunning -and $Mt5Connected -and $PublicLiveOk -and $CloudflaredCount -eq 1) {
    return "HEALTHY"
  }
  return "DEGRADED"
}

function Test-PublicGatewayLive {
  param([int]$TimeoutSec = 8)
  try {
    $h = Invoke-RestMethod -Uri $script:PublicLiveUri -TimeoutSec $TimeoutSec
    return (Test-GatewayLivePayload -Payload $h)
  } catch {
    return $false
  }
}

function Test-GatewayLivePayload {
  param($Payload)
  if ($null -eq $Payload) { return $false }
  if ($Payload.status -ne "ok") { return $false }
  if ($Payload.service -ne "mt5-gateway") { return $false }
  if ($null -ne $Payload.PSObject.Properties["probe"] -and [string]$Payload.probe -ne "" -and [string]$Payload.probe -ne "live") {
    return $false
  }
  return $true
}

function Test-LocalGatewayLiveOk {
  param([int]$TimeoutSec = 3)
  try {
    $h = Invoke-RestMethod "http://127.0.0.1:8765/health/live" -TimeoutSec $TimeoutSec
    return (Test-GatewayLivePayload -Payload $h)
  } catch {
    return $false
  }
}

function Get-Mt5TerminalCandidatePaths {
  return @(
    "C:\Program Files\MetaTrader 5\terminal64.exe",
    "C:\Program Files\Meta Trader 5\terminal64.exe"
  )
}

function Resolve-Mt5TerminalPath {
  param([string]$Preferred = "")
  if (-not [string]::IsNullOrWhiteSpace($Preferred) -and (Test-Path -LiteralPath $Preferred)) {
    return $Preferred
  }
  $envPath = ($env:MT5_TERMINAL_PATH | ForEach-Object { "$_" })
  if (-not [string]::IsNullOrWhiteSpace($envPath) -and (Test-Path -LiteralPath $envPath.Trim())) {
    return $envPath.Trim()
  }
  foreach ($candidate in @(Get-Mt5TerminalCandidatePaths)) {
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }
  if (-not [string]::IsNullOrWhiteSpace($Preferred)) { return $Preferred }
  return "C:\Program Files\MetaTrader 5\terminal64.exe"
}

function Get-SysinternalsAutologonPath {
  $names = @("Autologon64.exe", "Autologon64a.exe", "Autologon.exe")
  $dirs = @(
    "C:\Sysinternals",
    "C:\Tools",
    "C:\Tools\Sysinternals",
    "C:\Program Files\Sysinternals",
    "C:\Program Files\Windows Sysinternals",
    (Join-Path $env:SystemRoot "Sysinternals"),
    "C:\QuantForg\tools",
    (Join-Path $PSScriptRoot "tools")
  )
  foreach ($dir in $dirs) {
    foreach ($name in $names) {
      $p = Join-Path $dir $name
      if (Test-Path -LiteralPath $p) { return $p }
    }
  }
  return ""
}

function Get-LocalAdministratorState {
  $result = [ordered]@{
    Exists = $false
    Enabled = $false
    PasswordConfigured = $false
    Name = "Administrator"
  }
  try {
    $u = Get-LocalUser -Name "Administrator" -ErrorAction Stop
    $result.Exists = $true
    $result.Name = [string]$u.Name
    $result.Enabled = [bool]$u.Enabled
    $result.PasswordConfigured = ($null -ne $u.PasswordLastSet)
  } catch {
    $result.Exists = $false
  }
  return $result
}

# Local SAM Autologon identity. Never returns a password.
# Domain must be "." for local Administrator. DNS hostnames (example: US-HOST-421124)
# are invalid Autologon domains and make Sysinternals Autologon report invalid credentials.
function Get-LocalAutologonIdentity {
  $AutoLogonUser = "Administrator"
  $AutoLogonDomain = "."
  return [ordered]@{
    Username = $AutoLogonUser
    Domain = $AutoLogonDomain
    AccountType = "local"
  }
}

# True when Winlogon DefaultDomainName is set to something other than local SAM ".".
# US-HOST-421124 and any other hostname/NetBIOS/USERDOMAIN value is incorrect for local Administrator.
function Test-IsIncorrectLocalAutologonDomain {
  param([string]$Domain)
  if ([string]::IsNullOrWhiteSpace($Domain)) { return $false }
  if ($Domain -eq ".") { return $false }
  return $true
}

function Test-AutologonDomainLooksLikeRejectedDnsHostname {
  param([string]$Domain)
  return (Test-IsIncorrectLocalAutologonDomain -Domain $Domain)
}

# Writes only non-secret Winlogon identity. Never writes AutoAdminLogon or DefaultPassword.
function Set-AutologonNonSecretIdentity {
  $AutoLogonUser = "Administrator"
  $AutoLogonDomain = "."
  $keyPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
  if (-not (Test-Path -LiteralPath $keyPath)) { return $false }
  try {
    Set-ItemProperty -LiteralPath $keyPath -Name "DefaultUserName" -Value $AutoLogonUser -Type String -ErrorAction Stop
    Set-ItemProperty -LiteralPath $keyPath -Name "DefaultDomainName" -Value $AutoLogonDomain -Type String -ErrorAction Stop
    return $true
  } catch {
    return $false
  }
}

function Write-AutologonOperatorInstructions {
  $AutoLogonUser = "Administrator"
  $AutoLogonDomain = "."
  Write-Host ("Username={0}" -f $AutoLogonUser)
  Write-Host ("Domain={0}" -f $AutoLogonDomain)
  Write-Host "Password=dialog only"
  Write-Host ("Username = {0}" -f $AutoLogonUser)
  Write-Host ("Domain   = {0}" -f $AutoLogonDomain)
  Write-Host "Password = enter only in that dialog, then Enable."
}

# Auto-logon inspection. NEVER reads or prints DefaultPassword / LSA secret values.
# READY when AutoAdminLogon=1 and DefaultUserName is set, including LSA-protected
# Autologon where the Winlogon DefaultPassword value name is absent.
# Domain="." is a valid local-account DefaultDomainName and is not ACTION_REQUIRED.
function Get-AutoLogonReadiness {
  $interactive = [string]$env:USERNAME
  $identity = Get-LocalAutologonIdentity
  $result = [ordered]@{
    State = "ACTION_REQUIRED"
    Enabled = $false
    UserConfigured = $false
    DomainConfigured = $false
    PasswordValuePresent = $false
    SecretStorage = "none"
    DefaultUserName = ""
    DefaultDomainName = ""
    InteractiveUser = $interactive
    AutologonBinary = (Get-SysinternalsAutologonPath)
    RecommendedUsername = $identity.Username
    RecommendedDomain = $identity.Domain
    AccountType = $identity.AccountType
    IncorrectLocalAutologonDomain = $false
    LocalDomainIsDot = $false
  }
  try {
    $keyPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
    if (-not (Test-Path -LiteralPath $keyPath)) {
      $result.State = "NOT_SUPPORTED"
      return $result
    }
    $key = Get-Item $keyPath -ErrorAction Stop
    $auto = [string]$key.GetValue("AutoAdminLogon")
    $user = [string]$key.GetValue("DefaultUserName")
    $domain = [string]$key.GetValue("DefaultDomainName")
    $pwdPresent = $false
    foreach ($name in @($key.GetValueNames())) {
      if ($name -eq "DefaultPassword") { $pwdPresent = $true; break }
    }
    $result.Enabled = ($auto -eq "1")
    $result.UserConfigured = -not [string]::IsNullOrWhiteSpace($user)
    $result.DomainConfigured = -not [string]::IsNullOrWhiteSpace($domain)
    $result.PasswordValuePresent = $pwdPresent
    $result.DefaultUserName = $user
    $result.DefaultDomainName = $domain
    $result.LocalDomainIsDot = ($domain -eq ".")
    $result.IncorrectLocalAutologonDomain = (Test-IsIncorrectLocalAutologonDomain -Domain $domain)
    if ($result.Enabled -and $result.UserConfigured) {
      $result.State = "READY"
      if ($pwdPresent) { $result.SecretStorage = "winlogon_value_name_present" }
      else { $result.SecretStorage = "lsa_or_external" }
    } else {
      $result.State = "ACTION_REQUIRED"
      $result.SecretStorage = "none"
    }
  } catch {
    $result.State = "ERROR"
  }
  return $result
}

function Get-CloudflaredCommandSanitized {
  try {
    $svc = Get-CimInstance Win32_Service -Filter "Name='Cloudflared'" -ErrorAction SilentlyContinue
    if ($null -eq $svc) { return "missing" }
    $path = [string]$svc.PathName
    if ($path -match "--token\s+\S+" -and $path -notmatch "token-file") {
      return "inline_token_redacted"
    }
    if ($path -match "token-file") {
      return "cloudflared tunnel run --token-file (contents not logged)"
    }
    if ($path -match "cloudflared") {
      return "cloudflared (bin path present; token not logged)"
    }
    return "unexpected_command"
  } catch {
    return "unreadable"
  }
}

function Test-CloudflaredScmRestartConfigured {
  try {
    $out = (& sc.exe qfailure Cloudflared 2>$null | Out-String)
    if ([string]::IsNullOrWhiteSpace($out)) { return $false }
    return ($out -match "Restart")
  } catch {
    return $false
  }
}

function Set-CloudflaredScmRestartOnFailure {
  # First/second/subsequent failure: restart after 60s. Reset fail count daily.
  # Does not log the service binary command line (may include flags).
  $null = & sc.exe failure Cloudflared reset= 86400 actions= restart/60000/restart/60000/restart/60000
  return $LASTEXITCODE
}

function Test-WatchdogGatewayStartAllowed {
  param(
    [string]$StateFile,
    [int]$MaxPerHour = 8
  )
  if (-not (Test-Path $StateFile)) { return $true }
  $starts = 0
  $window = $null
  foreach ($line in @(Get-Content $StateFile -ErrorAction SilentlyContinue)) {
    if ($line -match "^starts_in_window=(\d+)") { $starts = [int]$Matches[1] }
    if ($line -match "^start_window_utc=(.+)$") {
      try { $window = [datetime]$Matches[1] } catch { $window = $null }
    }
  }
  if ($null -eq $window) { return $true }
  if (([datetime]::UtcNow - $window.ToUniversalTime()).TotalHours -ge 1) { return $true }
  return ($starts -lt $MaxPerHour)
}

function Get-WatchdogStartCounters {
  param([string]$StateFile)
  $starts = 0
  $window = [datetime]::UtcNow
  if (Test-Path $StateFile) {
    foreach ($line in @(Get-Content $StateFile -ErrorAction SilentlyContinue)) {
      if ($line -match "^starts_in_window=(\d+)") { $starts = [int]$Matches[1] }
      if ($line -match "^start_window_utc=(.+)$") {
        try { $window = [datetime]$Matches[1] } catch { $window = [datetime]::UtcNow }
      }
    }
  }
  if (([datetime]::UtcNow - $window.ToUniversalTime()).TotalHours -ge 1) {
    $starts = 0
    $window = [datetime]::UtcNow
  }
  return @{ Starts = $starts; WindowUtc = $window.ToUniversalTime() }
}

function Get-ProviderPowerMarkerPath {
  return (Join-Path $env:ProgramData "QuantForg\provider_power_recovery.ready")
}

# Guest OS cannot read hypervisor/BIOS power-on policy. READY only after operator attestation.
function Get-ProviderPowerReadiness {
  $result = [ordered]@{
    State = "UNKNOWN"
    MarkerPath = (Get-ProviderPowerMarkerPath)
    Attested = $false
  }
  $path = $result.MarkerPath
  if (-not (Test-Path -LiteralPath $path)) {
    return $result
  }
  $confirmed = $false
  foreach ($line in @(Get-Content -LiteralPath $path -ErrorAction SilentlyContinue)) {
    if ($line -match "^confirmed=true\s*$") { $confirmed = $true }
  }
  if ($confirmed) {
    $result.Attested = $true
    $result.State = "READY"
  } else {
    $result.State = "UNKNOWN"
  }
  return $result
}
