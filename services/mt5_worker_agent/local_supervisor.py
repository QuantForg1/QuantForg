"""Local multi-slot worker supervisor for the existing Windows machine.

Manages isolated portable slots independently. Failure of one slot must not
stop others. Does not enable LIVE multi-user order submission.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from services.mt5_worker_agent.paths import slot_terminal_exe
from services.mt5_worker_agent.railway_client import (
    RailwayClientConfig,
    RailwayWorkerClient,
)
from services.mt5_worker_agent.resources import (
    host_memory_summary,
    sample_terminal_processes,
)
from services.mt5_worker_agent.slot_manager import (
    list_configured_slot_ids,
    prepare_portable_slot,
    slot_status,
    start_slot_terminal,
    stop_slot_terminal,
)

logger = logging.getLogger("quantforg.mt5_worker_agent.supervisor")


@dataclass
class SlotRuntimeState:
    slot_id: str
    prepared: bool = False
    terminal_pid: int | None = None
    lifecycle: str = "pending"
    ready: bool = False
    last_error: str = ""
    last_heartbeat_at: str | None = None
    verified_login: str = ""
    verified_server: str = ""


@dataclass
class LocalWorkerSupervisor:
    host_code: str = field(
        default_factory=lambda: (
            os.environ.get("QF_WORKER_HOST_CODE") or "local-windows-1"
        )
    )
    slot_ids: list[str] = field(default_factory=list)
    states: dict[str, SlotRuntimeState] = field(default_factory=dict)
    railway: RailwayWorkerClient | None = None

    def __post_init__(self) -> None:
        if not self.slot_ids:
            self.slot_ids = list_configured_slot_ids()
        for slot_id in self.slot_ids:
            self.states[slot_id] = SlotRuntimeState(slot_id=slot_id)
        if self.railway is None:
            try:
                self.railway = RailwayWorkerClient(RailwayClientConfig.from_env())
            except ValueError as exc:
                logger.warning("railway_client_unavailable reason=%s", exc)

    def prepare_all(self, *, force: bool = False) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for slot_id in self.slot_ids:
            try:
                path = prepare_portable_slot(slot_id, force=force)
                self.states[slot_id].prepared = True
                self.states[slot_id].lifecycle = "provisioning"
                results[slot_id] = {"ok": True, "path": str(path)}
            except Exception as exc:
                self.states[slot_id].last_error = type(exc).__name__
                self.states[slot_id].lifecycle = "error"
                results[slot_id] = {"ok": False, "error": type(exc).__name__}
                logger.exception("prepare_slot_failed slot=%s", slot_id)
        return results

    def start_all_terminals(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for slot_id in self.slot_ids:
            try:
                pid = start_slot_terminal(slot_id)
                st = self.states[slot_id]
                st.terminal_pid = pid
                st.lifecycle = "starting"
                st.ready = False
                results[slot_id] = {"ok": True, "pid": pid}
            except Exception as exc:
                self.states[slot_id].last_error = type(exc).__name__
                self.states[slot_id].lifecycle = "error"
                results[slot_id] = {"ok": False, "error": type(exc).__name__}
                logger.exception("start_slot_failed slot=%s", slot_id)
        return results

    def stop_slot(self, slot_id: str) -> bool:
        ok = stop_slot_terminal(slot_id)
        st = self.states[slot_id]
        st.lifecycle = "stopped"
        st.ready = False
        st.terminal_pid = None
        return ok

    def stop_all(self) -> dict[str, bool]:
        return {slot_id: self.stop_slot(slot_id) for slot_id in self.slot_ids}

    def refresh_status(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for slot_id in self.slot_ids:
            status = slot_status(slot_id)
            st = self.states[slot_id]
            st.prepared = status.prepared
            st.terminal_pid = status.pid
            rows.append(
                {
                    "slot_id": slot_id,
                    "prepared": status.prepared,
                    "portable": status.portable,
                    "process_running": status.process_running,
                    "pid": status.pid,
                    "lifecycle": st.lifecycle,
                    "ready": st.ready,
                    "last_error": st.last_error,
                    "terminal_exe": status.terminal_exe,
                }
            )
        return rows

    def heartbeat_once(self) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        payload: dict[str, Any] = {
            "host_code": self.host_code,
            "at": now,
            "slots": self.refresh_status(),
            "resources": {
                "terminals": [
                    {
                        "pid": s.pid,
                        "exe_path": s.exe_path,
                        "working_set_mb": s.working_set_mb,
                        "cpu_seconds": s.cpu_seconds,
                    }
                    for s in sample_terminal_processes()
                ],
                "host_memory": host_memory_summary(),
            },
        }
        for slot_id, st in self.states.items():
            st.last_heartbeat_at = now
            if self.railway is not None:
                self.railway.heartbeat(
                    worker_id=f"{self.host_code}:{slot_id}",
                    slot_id=slot_id,
                    lifecycle=st.lifecycle,
                    ready=st.ready,
                )
        return payload

    def run_forever(self, *, interval_seconds: float = 30.0) -> None:
        logger.info(
            "local_supervisor_start host=%s slots=%s",
            self.host_code,
            ",".join(self.slot_ids),
        )
        while True:
            report = self.heartbeat_once()
            ready_count = sum(1 for s in report["slots"] if s.get("ready"))
            running = sum(1 for s in report["slots"] if s.get("process_running"))
            logger.info(
                "local_supervisor_tick ready=%s running=%s terminals=%s",
                ready_count,
                running,
                len(report["resources"]["terminals"]),
            )
            time.sleep(interval_seconds)

    def terminal_exe_for(self, slot_id: str) -> str:
        return str(slot_terminal_exe(slot_id))
