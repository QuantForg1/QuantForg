"""Host resource snapshot — observability only.

Does not change trading thresholds. Does not kill processes.
Warning vs critical bands are configurable via environment.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def ram_warn_pct() -> float:
    return _env_float("QUANTFORG_INFRA_RAM_WARN_PCT", 80.0)


def ram_critical_pct() -> float:
    return _env_float("QUANTFORG_INFRA_RAM_CRITICAL_PCT", 95.0)


def disk_warn_pct() -> float:
    return _env_float("QUANTFORG_INFRA_DISK_WARN_PCT", 85.0)


def disk_critical_pct() -> float:
    return _env_float("QUANTFORG_INFRA_DISK_CRITICAL_PCT", 95.0)


def _linux_mem() -> tuple[float | None, int | None, int | None]:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return None, None, None
    data: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.replace(":", " ").split()
        if len(parts) >= 2 and parts[1].isdigit():
            data[parts[0]] = int(parts[1]) * 1024
    total = data.get("MemTotal")
    available = data.get("MemAvailable")
    if not total or available is None:
        return None, total, available
    used = total - available
    return round(100.0 * used / total, 2), total, available


def _windows_mem() -> tuple[float | None, int | None, int | None]:
    try:
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return None, None, None
        return (
            float(stat.dwMemoryLoad),
            int(stat.ullTotalPhys),
            int(stat.ullAvailPhys),
        )
    except Exception:
        return None, None, None


def _cpu_load_pct() -> float | None:
    load: float | None = None
    getter = getattr(os, "getloadavg", None)
    if callable(getter):
        try:
            load = float(getter()[0])
        except OSError:
            load = None
    cpus = os.cpu_count() or 1
    if load is None:
        return None
    return round(100.0 * load / max(1, cpus), 2)


def _band(pct: float | None, warn: float, critical: float) -> str:
    if pct is None:
        return "UNKNOWN"
    if pct >= critical:
        return "CRITICAL"
    if pct >= warn:
        return "WARNING"
    return "OK"


def _process_count() -> int | None:
    try:
        proc = Path("/proc")
        if proc.is_dir():
            return sum(1 for p in proc.iterdir() if p.name.isdigit())
    except Exception:
        return None
    return None


def collect_resource_snapshot() -> dict[str, Any]:
    """Best-effort host snapshot. Never raises into the trading path."""
    ram_pct, ram_total, ram_avail = _linux_mem()
    if ram_pct is None:
        ram_pct, ram_total, ram_avail = _windows_mem()
    disk_pct: float | None = None
    disk_total = disk_free = None
    try:
        usage = shutil.disk_usage(os.getcwd() or ".")
        disk_total = int(usage.total)
        disk_free = int(usage.free)
        if usage.total:
            disk_pct = round(100.0 * (usage.used / usage.total), 2)
    except Exception:
        disk_pct = None
    cpu_pct = _cpu_load_pct()
    ram_band = _band(ram_pct, ram_warn_pct(), ram_critical_pct())
    disk_band = _band(disk_pct, disk_warn_pct(), disk_critical_pct())
    cpu_band = _band(cpu_pct, 85.0, 98.0)
    critical = ram_band == "CRITICAL" or disk_band == "CRITICAL"
    return {
        "cpu_load_pct": cpu_pct,
        "cpu_band": cpu_band,
        "ram_used_pct": ram_pct,
        "ram_total_bytes": ram_total,
        "ram_available_bytes": ram_avail,
        "ram_band": ram_band,
        "ram_warn_pct": ram_warn_pct(),
        "ram_critical_pct": ram_critical_pct(),
        "disk_used_pct": disk_pct,
        "disk_total_bytes": disk_total,
        "disk_free_bytes": disk_free,
        "disk_band": disk_band,
        "disk_warn_pct": disk_warn_pct(),
        "disk_critical_pct": disk_critical_pct(),
        "process_count": _process_count(),
        "critical": critical,
        "modifies_trading_thresholds": False,
        "kills_processes": False,
    }
