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
    worker_id: str = ""
    railway_ok: bool = False
    revoked: bool = False


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
                    "worker_id": st.worker_id,
                    "railway_ok": st.railway_ok,
                    "revoked": st.revoked,
                }
            )
        return rows

    def register_with_railway(self) -> dict[str, Any]:
        """Register host + each slot with the Railway control plane."""
        if self.railway is None:
            return {"ok": False, "error": "railway_client_unavailable"}
        host = self.railway.register_host(
            host_code=self.host_code,
            max_terminals=max(4, len(self.slot_ids)),
        )
        results: dict[str, Any] = {"host": host, "slots": {}}
        for slot_id in self.slot_ids:
            st = self.states[slot_id]
            if st.revoked:
                results["slots"][slot_id] = {"ok": False, "error": "revoked"}
                continue
            resp = self.railway.register_worker(
                host_code=self.host_code, slot_id=slot_id
            )
            ok = bool(resp.get("ok")) and bool(resp.get("worker_id"))
            if ok:
                st.worker_id = str(resp["worker_id"])
                st.railway_ok = True
                st.lifecycle = str(resp.get("lifecycle") or st.lifecycle)
                st.revoked = bool(resp.get("revoked"))
            else:
                st.railway_ok = False
                st.last_error = str(resp.get("error") or "register_failed")
            results["slots"][slot_id] = resp
            logger.info(
                "railway_register slot=%s ok=%s worker_id=%s",
                slot_id,
                ok,
                st.worker_id or "-",
            )
        return {"ok": all(v.get("ok") for v in results["slots"].values()), **results}

    def fetch_assignments(self) -> dict[str, Any]:
        if self.railway is None:
            return {"ok": False, "error": "railway_client_unavailable"}
        out: dict[str, Any] = {}
        for slot_id, st in self.states.items():
            if not st.worker_id:
                out[slot_id] = {"ok": False, "error": "not_registered"}
                continue
            resp = self.railway.get_assignment(worker_id=st.worker_id)
            if resp.get("status") == 401 or resp.get("status") == 403:
                st.revoked = True
                st.railway_ok = False
            out[slot_id] = resp
        return out

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
            "railway": {},
        }
        for slot_id, st in self.states.items():
            st.last_heartbeat_at = now
            if self.railway is None or not st.worker_id or st.revoked:
                continue
            hb = self.railway.heartbeat(
                worker_id=st.worker_id,
                slot_id=slot_id,
                lifecycle=st.lifecycle,
                ready=st.ready,
            )
            payload["railway"][slot_id] = {
                "ok": bool(hb.get("ok")),
                "status": hb.get("status"),
                "error": hb.get("error"),
            }
            if hb.get("status") in {401, 403} or hb.get("revoked"):
                st.revoked = True
                st.railway_ok = False
                st.last_error = "revoked_or_unauthorized"
                logger.warning("railway_heartbeat_revoked slot=%s", slot_id)
            elif hb.get("ok"):
                st.railway_ok = True
            else:
                st.railway_ok = False
                # Network blip — keep worker_id for reconnect; do not clear.
                logger.warning(
                    "railway_heartbeat_failed slot=%s error=%s",
                    slot_id,
                    hb.get("error"),
                )
        return payload

    def run_forever(self, *, interval_seconds: float = 30.0) -> None:
        logger.info(
            "local_supervisor_start host=%s slots=%s",
            self.host_code,
            ",".join(self.slot_ids),
        )
        if self.railway is not None:
            reg = self.register_with_railway()
            logger.info(
                "railway_register_complete ok=%s",
                reg.get("ok"),
            )
        while True:
            report = self.heartbeat_once()
            ready_count = sum(1 for s in report["slots"] if s.get("ready"))
            running = sum(1 for s in report["slots"] if s.get("process_running"))
            railway_ok = sum(1 for s in report["slots"] if s.get("railway_ok"))
            logger.info(
                "local_supervisor_tick ready=%s running=%s railway_ok=%s terminals=%s",
                ready_count,
                running,
                railway_ok,
                len(report["resources"]["terminals"]),
            )
            time.sleep(interval_seconds)

    def terminal_exe_for(self, slot_id: str) -> str:
        return str(slot_terminal_exe(slot_id))
