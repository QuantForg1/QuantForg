"""Local resource probes for MT5 terminals (no secrets)."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_POWERSHELL = str(
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
    / "System32"
    / "WindowsPowerShell"
    / "v1.0"
    / "powershell.exe"
)


@dataclass(frozen=True, slots=True)
class TerminalResourceSample:
    pid: int
    exe_path: str
    working_set_mb: float
    cpu_seconds: float


def sample_terminal_processes() -> list[TerminalResourceSample]:
    script = r"""
$procs = Get-Process -Name terminal64,terminal -ErrorAction SilentlyContinue
$out = @()
foreach ($p in $procs) {
  $path = $null
  try {
    $path = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)").ExecutablePath
  } catch {}
  $out += [pscustomobject]@{
    pid = $p.Id
    exe_path = $path
    working_set_mb = [math]::Round($p.WorkingSet64 / 1MB, 2)
    cpu_seconds = [math]::Round([double]$p.CPU, 2)
  }
}
$out | ConvertTo-Json -Compress
"""
    try:
        completed = subprocess.run(  # noqa: S603
            [
                _POWERSHELL,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    raw = (completed.stdout or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rows = data if isinstance(data, list) else [data]
    samples: list[TerminalResourceSample] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            samples.append(
                TerminalResourceSample(
                    pid=int(row["pid"]),
                    exe_path=str(row.get("exe_path") or ""),
                    working_set_mb=float(row.get("working_set_mb") or 0),
                    cpu_seconds=float(row.get("cpu_seconds") or 0),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return samples


def host_memory_summary() -> dict[str, Any]:
    script = r"""
$os = Get-CimInstance Win32_OperatingSystem
[pscustomobject]@{
  total_mb = [math]::Round($os.TotalVisibleMemorySize / 1024, 2)
  free_mb = [math]::Round($os.FreePhysicalMemory / 1024, 2)
} | ConvertTo-Json -Compress
"""
    try:
        completed = subprocess.run(  # noqa: S603
            [_POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads((completed.stdout or "").strip() or "{}")
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}
