# Shared Gateway process-tree helpers for Windows VPS scripts.
# Dot-source from supervise/verify/recover. NEVER sends broker orders.

$script:GatewayPort = 8765
$script:GatewayCmdPattern = "services\.mt5_gateway\.main"

function Test-GatewayCommandLine {
  param([string]$CommandLine)
  if ([string]::IsNullOrWhiteSpace($CommandLine)) { return $false }
  return [bool]($CommandLine -match $script:GatewayCmdPattern)
}

function Get-GatewayListenPids {
  # Invariant: LISTENING owners of 127.0.0.1:8765 only.
  $pids = @()
  $lines = & netstat -ano -p tcp 2>$null
  foreach ($line in $lines) {
    if ($line -match "127\.0\.0\.1:$($script:GatewayPort)\s+\S+\s+LISTENING\s+(\d+)\s*$") {
      $pids += [int]$Matches[1]
    }
  }
  return @($pids | Select-Object -Unique)
}

function Get-Win32ById {
  param([int]$ProcessId)
  if ($ProcessId -le 0) { return $null }
  return Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
}

function Get-GatewayTreeRoot {
  param([int]$ProcessId)
  $current = $ProcessId
  for ($i = 0; $i -lt 8; $i++) {
    $proc = Get-Win32ById -ProcessId $current
    if ($null -eq $proc) { break }
    $parentId = [int]$proc.ParentProcessId
    if ($parentId -le 0) { break }
    $parent = Get-Win32ById -ProcessId $parentId
    if ($null -eq $parent) { break }
    if (-not (Test-GatewayCommandLine -CommandLine ([string]$parent.CommandLine))) { break }
    $current = $parentId
  }
  return $current
}

function Get-GatewayTreePids {
  param([int]$RootPid)
  $found = New-Object System.Collections.Generic.List[int]
  if ($RootPid -le 0) { return @() }
  $queue = New-Object System.Collections.Generic.Queue[int]
  $queue.Enqueue($RootPid)
  $seen = @{}
  while ($queue.Count -gt 0) {
    $id = $queue.Dequeue()
    if ($seen.ContainsKey($id)) { continue }
    $seen[$id] = $true
    $found.Add($id)
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$id" -ErrorAction SilentlyContinue)
    foreach ($child in $children) {
      $cid = [int]$child.ProcessId
      if ($cid -le 0) { continue }
      $name = [string]$child.Name
      $cmd = [string]$child.CommandLine
      if ((Test-GatewayCommandLine -CommandLine $cmd) -or ($name -match "^python")) {
        $queue.Enqueue($cid)
      }
    }
  }
  return @($found | Select-Object -Unique)
}

function Get-IndependentGatewayTreeRoots {
  param([int[]]$ListenPids)
  $roots = @()
  foreach ($lp in @($ListenPids)) {
    if ($lp -le 0) { continue }
    $roots += (Get-GatewayTreeRoot -ProcessId $lp)
  }
  return @($roots | Select-Object -Unique)
}

function Write-GatewayPidFile {
  param(
    [string]$Path,
    [int]$ListenerPid,
    [int]$TreeRootPid
  )
  $tree = @(Get-GatewayTreePids -RootPid $TreeRootPid)
  $treeText = ($tree -join ",")
  @(
    "listener=$ListenerPid",
    "tree_root=$TreeRootPid",
    "tree=$treeText"
  ) | Set-Content -Path $Path -Encoding ASCII
}

function Stop-GatewayProcessTree {
  param(
    [int[]]$ListenPids,
    [string]$LogFunc = ""
  )
  $roots = @(Get-IndependentGatewayTreeRoots -ListenPids $ListenPids)
  foreach ($root in $roots) {
    if ($root -le 0) { continue }
    $tree = @(Get-GatewayTreePids -RootPid $root)
    $msg = "stopping gateway tree root={0} pids={1}" -f $root, ($tree -join ",")
    if ($LogFunc -eq "") {
      Write-Host $msg
    }
    # /T from the launcher root so parent+child both exit.
    & taskkill.exe /F /T /PID $root 2>$null | Out-Null
  }
  Start-Sleep -Seconds 2
}
