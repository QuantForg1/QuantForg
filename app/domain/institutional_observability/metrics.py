"""Process metrics + uptime — observability only, never mutates systems."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any

_PROCESS_STARTED_AT = datetime.now(UTC)
_RESTART_HISTORY: list[dict[str, Any]] = [
    {
        "timestamp": _PROCESS_STARTED_AT.isoformat().replace("+00:00", "Z"),
        "event": "process_start",
        "pid": os.getpid(),
    }
]


def process_started_at() -> datetime:
    return _PROCESS_STARTED_AT


def record_restart_marker(*, reason: str = "observed") -> dict[str, Any]:
    """Append an observability restart marker — does not restart anything."""
    entry = {
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "event": "restart_marker",
        "reason": reason,
        "pid": os.getpid(),
    }
    _RESTART_HISTORY.append(entry)
    return entry


def collect_resource_metrics() -> dict[str, Any]:
    """Best-effort CPU/memory/disk/network — nulls when unavailable."""
    out: dict[str, Any] = {
        "cpu_percent": None,
        "memory_percent": None,
        "memory_used_mb": None,
        "disk_percent": None,
        "network_bytes_sent": None,
        "network_bytes_recv": None,
        "open_connections": None,
        "queue_depth": None,
        "database": {"status": "unknown", "note": "not probed — never invents"},
        "cache": {"status": "unknown", "note": "not probed — never invents"},
        "source": "unavailable",
    }
    try:
        import psutil  # type: ignore[import-untyped]

        proc = psutil.Process(os.getpid())
        out["cpu_percent"] = float(proc.cpu_percent(interval=0.05))
        mem = proc.memory_info()
        out["memory_used_mb"] = round(mem.rss / (1024 * 1024), 2)
        out["memory_percent"] = float(proc.memory_percent())
        try:
            disk = psutil.disk_usage(".")
            out["disk_percent"] = float(disk.percent)
        except Exception:
            out["disk_percent"] = None
        try:
            net = psutil.net_io_counters()
            out["network_bytes_sent"] = int(net.bytes_sent)
            out["network_bytes_recv"] = int(net.bytes_recv)
        except Exception:
            out["network_bytes_sent"] = None
            out["network_bytes_recv"] = None
        try:
            out["open_connections"] = len(proc.connections(kind="inet"))
        except Exception:
            out["open_connections"] = None
        out["source"] = "psutil"
    except Exception:
        # Fallback without psutil
        out["source"] = "basic"
        out["memory_used_mb"] = None
    out["pid"] = os.getpid()
    out["observed_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return out


def compute_uptime() -> dict[str, Any]:
    now = datetime.now(UTC)
    started = _PROCESS_STARTED_AT
    current_sec = max(0.0, (now - started).total_seconds())
    # Window ratios assume continuous process — never fabricate historical uptime
    return {
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "current_uptime_seconds": round(current_sec, 1),
        "uptime_24h_ratio": (
            round(min(1.0, current_sec / 86_400), 4) if current_sec else 0.0
        ),
        "uptime_7d_ratio": (
            round(min(1.0, current_sec / 604_800), 4) if current_sec else 0.0
        ),
        "uptime_30d_ratio": (
            round(min(1.0, current_sec / 2_592_000), 4) if current_sec else 0.0
        ),
        "restart_history": list(_RESTART_HISTORY[-50:]),
        "note": (
            "24h/7d/30d ratios reflect this process lifetime only — "
            "never invents multi-process historical uptime"
        ),
    }


def measure_latency_ms(fn) -> float | None:
    """Time a callable; return None on failure — never invents latency."""
    try:
        t0 = time.perf_counter()
        fn()
        return round((time.perf_counter() - t0) * 1000.0, 3)
    except Exception:
        return None
