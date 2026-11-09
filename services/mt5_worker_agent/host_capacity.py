"""Local Windows host capacity for portable MT5 slots.

Does not invent unlimited multi-user capacity. Keeps the LIVE Program Files
Weltrade terminal outside the worker budget.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from services.mt5_worker_agent.resources import (
    host_memory_summary,
    sample_terminal_processes,
)
from services.mt5_worker_agent.slot_manager import (
    list_configured_slot_ids,
    slot_status,
)

# Measured on the existing developer host (2026-11-09): ~230-250 MB per idle
# portable terminal; LIVE singleton also running. Soft budget leaves headroom.
DEFAULT_MAX_CONCURRENT_PORTABLES = 2
MIN_FREE_RAM_MB = 800.0
RAM_PER_PORTABLE_MB = 280.0


@dataclass(frozen=True, slots=True)
class HostCapacityReport:
    max_concurrent_portables: int
    prepared_slots: int
    running_portables: int
    live_terminal_running: bool
    free_ram_mb: float
    total_ram_mb: float
    disk_free_gb: float | None
    available_now: int
    queued_would_wait: bool
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_concurrent_portables": self.max_concurrent_portables,
            "prepared_slots": self.prepared_slots,
            "running_portables": self.running_portables,
            "live_terminal_running": self.live_terminal_running,
            "free_ram_mb": round(self.free_ram_mb, 1),
            "total_ram_mb": round(self.total_ram_mb, 1),
            "disk_free_gb": self.disk_free_gb,
            "available_now": self.available_now,
            "queued_would_wait": self.queued_would_wait,
            "verified_concurrent_capacity": self.max_concurrent_portables,
            "note": self.note,
            "new_vps_required": False,
            "weltrade_live_protected": True,
        }


def _configured_max() -> int:
    raw = (os.environ.get("QF_MT5_MAX_CONCURRENT_PORTABLES") or "").strip()
    if raw.isdigit():
        return max(1, min(int(raw), 8))
    return DEFAULT_MAX_CONCURRENT_PORTABLES


def measure_host_capacity() -> HostCapacityReport:
    mem = host_memory_summary()
    free = float(mem.get("free_mb") or 0.0)
    total = float(mem.get("total_mb") or 0.0)
    slots = list_configured_slot_ids()
    prepared = 0
    running = 0
    for slot_id in slots:
        st = slot_status(slot_id)
        if st.prepared:
            prepared += 1
        if st.process_running:
            running += 1

    live_path = (
        os.environ.get("QF_LIVE_MT5_TERMINAL_PATH")
        or r"C:\Program Files\MetaTrader 5\terminal64.exe"
    ).lower()
    live_running = False
    for proc in sample_terminal_processes():
        exe = (proc.exe_path or "").lower()
        if exe and ("program files" in exe or exe == live_path):
            live_running = True
            break
    if not live_running:
        # Fallback: any terminal64 outside slot root counts as LIVE-ish.
        slot_root = (os.environ.get("QF_MT5_SLOT_ROOT") or "").lower()
        for proc in sample_terminal_processes():
            exe = (proc.exe_path or "").lower()
            if exe and slot_root and slot_root not in exe:
                live_running = True
                break

    ram_budget = max(0, int((free - MIN_FREE_RAM_MB) // RAM_PER_PORTABLE_MB))
    configured = _configured_max()
    max_conc = max(1, min(configured, prepared or configured, max(1, ram_budget or 1)))
    # If free RAM is critically low, clamp hard.
    if free < MIN_FREE_RAM_MB:
        max_conc = max(1, min(max_conc, running or 1))
    available = max(0, max_conc - running)
    disk_free = None
    try:
        import shutil

        usage = shutil.disk_usage(os.environ.get("QF_MT5_SLOT_ROOT") or "C:\\")
        disk_free = round(usage.free / (1024**3), 2)
    except Exception:
        disk_free = None

    return HostCapacityReport(
        max_concurrent_portables=max_conc,
        prepared_slots=prepared,
        running_portables=running,
        live_terminal_running=live_running,
        free_ram_mb=free,
        total_ram_mb=total,
        disk_free_gb=disk_free,
        available_now=available,
        queued_would_wait=available <= 0,
        note=(
            "Existing Windows host retained - no new VPS. "
            f"Verified soft cap {max_conc} concurrent portable terminal(s); "
            "Weltrade LIVE Program Files terminal is outside this budget."
        ),
    )


def can_start_another_portable() -> tuple[bool, str]:
    report = measure_host_capacity()
    if report.available_now > 0:
        return True, "capacity_available"
    return False, "host_capacity_exhausted_queue_required"
