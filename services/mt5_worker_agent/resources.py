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


def process_image_path(pid: int) -> str:
    """Resolve executable path when CIM ExecutablePath is empty (common on locked-down hosts)."""
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return ""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    process_query_limited_information = 0x1000
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    query = kernel32.QueryFullProcessImageNameW
    query.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    query.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    handle = open_process(process_query_limited_information, False, int(pid))
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buf))
        if not query(handle, 0, buf, ctypes.byref(size)):
            return ""
        return str(buf.value or "")
    finally:
        close_handle(handle)


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
            pid = int(row["pid"])
            exe = str(row.get("exe_path") or "")
            if not exe:
                exe = process_image_path(pid)
            samples.append(
                TerminalResourceSample(
                    pid=pid,
                    exe_path=exe,
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
