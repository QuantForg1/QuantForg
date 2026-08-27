"""In-memory infrastructure heartbeats — observability only.

Never writes to the database. Never changes Opportunity/Risk/Safety/OMS.
Bounded retention: last state + counters only.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any

_STARTED_MONO = time.monotonic()
_STARTED_UTC = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

RAILWAY_ITE_HEARTBEAT = "RAILWAY_ITE_HEARTBEAT"
GATEWAY_HEARTBEAT = "GATEWAY_HEARTBEAT"
MT5_HEARTBEAT = "MT5_HEARTBEAT"
CLOUDFLARED_HEARTBEAT = "CLOUDFLARED_HEARTBEAT"

_NAMES = (
    RAILWAY_ITE_HEARTBEAT,
    GATEWAY_HEARTBEAT,
    MT5_HEARTBEAT,
    CLOUDFLARED_HEARTBEAT,
)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class HeartbeatState:
    name: str
    timestamp: str | None = None
    state: str = "UNKNOWN"
    last_successful_health_check: str | None = None
    failure_count: int = 0
    recovery_count: int = 0
    last_failure_reason: str | None = None
    _healthy: bool = field(default=False, repr=False)

    def to_dict(self, *, uptime_seconds: float) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "state": self.state,
            "uptime_seconds": round(uptime_seconds, 3),
            "last_successful_health_check": self.last_successful_health_check,
            "failure_count": self.failure_count,
            "recovery_count": self.recovery_count,
            "last_failure_reason": self.last_failure_reason,
        }


class InfrastructureHeartbeats:
    def __init__(self) -> None:
        self._lock = Lock()
        self._beats = {name: HeartbeatState(name=name) for name in _NAMES}

    def note(self, name: str, *, ok: bool, state: str, reason: str | None = None) -> None:
        if name not in self._beats:
            return
        now = _now()
        with self._lock:
            beat = self._beats[name]
            beat.timestamp = now
            beat.state = state
            was = beat._healthy
            if ok:
                beat.last_successful_health_check = now
                beat._healthy = True
                if not was and beat.failure_count > 0:
                    beat.recovery_count += 1
            else:
                beat._healthy = False
                beat.failure_count += 1
                if reason:
                    beat.last_failure_reason = str(reason)[:240]

    def snapshot(self) -> dict[str, Any]:
        uptime = time.monotonic() - _STARTED_MONO
        with self._lock:
            beats = {
                name: beat.to_dict(uptime_seconds=uptime)
                for name, beat in self._beats.items()
            }
        return {
            "process_started_at": _STARTED_UTC,
            "uptime_seconds": round(uptime, 3),
            "heartbeats": beats,
        }


_HEARTBEATS = InfrastructureHeartbeats()


def get_infrastructure_heartbeats() -> InfrastructureHeartbeats:
    return _HEARTBEATS


def note_heartbeat(
    name: str, *, ok: bool, state: str, reason: str | None = None
) -> None:
    _HEARTBEATS.note(name, ok=ok, state=state, reason=reason)


def heartbeat_snapshot() -> dict[str, Any]:
    return _HEARTBEATS.snapshot()
