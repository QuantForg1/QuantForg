"""Worker host capacity tracking (Phase 1B).

Prevents over-allocation of terminal slots. Does not invent running hosts —
operators register host capacity explicitly. Measured capacity for thousands
of sessions is not claimed until load tests prove it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID, uuid4

from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class WorkerHostCapacity:
    host_id: UUID
    host_code: str
    max_terminals: int
    allocated_terminals: int = 0
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    disk_percent: float = 0.0
    healthy: bool = True
    region: str = ""
    notes: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def free_slots(self) -> int:
        return max(0, self.max_terminals - self.allocated_terminals)

    @property
    def saturated(self) -> bool:
        return self.free_slots <= 0 or not self.healthy


@dataclass
class InMemoryCapacityManager:
    """Process-local capacity ledger for tests and control-plane dry runs."""

    _lock: Lock = field(default_factory=Lock)
    _hosts: dict[UUID, WorkerHostCapacity] = field(default_factory=dict)
    _codes: dict[str, UUID] = field(default_factory=dict)

    def reset(self) -> None:
        with self._lock:
            self._hosts.clear()
            self._codes.clear()

    def register_host(
        self,
        *,
        host_code: str,
        max_terminals: int,
        region: str = "",
        notes: str = "",
        host_id: UUID | None = None,
    ) -> WorkerHostCapacity:
        code = (host_code or "").strip()
        if not code:
            raise ValidationError(
                "host_code is required", details={"field": "host_code"}
            )
        if max_terminals < 1:
            raise ValidationError(
                "max_terminals must be >= 1",
                details={"max_terminals": max_terminals},
            )
        host = WorkerHostCapacity(
            host_id=host_id or uuid4(),
            host_code=code,
            max_terminals=int(max_terminals),
            region=(region or "").strip(),
            notes=(notes or "").strip(),
        )
        with self._lock:
            if code.lower() in self._codes:
                raise ConflictError(
                    "host_code already registered",
                    details={"host_code": code},
                )
            self._hosts[host.host_id] = host
            self._codes[code.lower()] = host.host_id
            return host

    def get(self, host_id: UUID) -> WorkerHostCapacity | None:
        with self._lock:
            return self._hosts.get(host_id)

    def list_hosts(self) -> list[WorkerHostCapacity]:
        with self._lock:
            return list(self._hosts.values())

    def update_metrics(
        self,
        host_id: UUID,
        *,
        cpu_percent: float,
        ram_percent: float,
        disk_percent: float,
        healthy: bool = True,
    ) -> WorkerHostCapacity:
        with self._lock:
            current = self._hosts.get(host_id)
            if current is None:
                raise NotFoundError(
                    "Worker host not found", details={"host_id": str(host_id)}
                )
            updated = WorkerHostCapacity(
                host_id=current.host_id,
                host_code=current.host_code,
                max_terminals=current.max_terminals,
                allocated_terminals=current.allocated_terminals,
                cpu_percent=float(cpu_percent),
                ram_percent=float(ram_percent),
                disk_percent=float(disk_percent),
                healthy=bool(healthy),
                region=current.region,
                notes=current.notes,
                updated_at=datetime.now(UTC),
            )
            self._hosts[host_id] = updated
            return updated

    def allocate_slot(self, host_id: UUID | None = None) -> WorkerHostCapacity:
        """Reserve one terminal slot. Prefer explicit host, else first free."""
        with self._lock:
            if host_id is not None:
                host = self._hosts.get(host_id)
                if host is None:
                    raise NotFoundError(
                        "Worker host not found", details={"host_id": str(host_id)}
                    )
                if host.saturated:
                    raise ConflictError(
                        "Worker host capacity exhausted",
                        details={
                            "host_id": str(host_id),
                            "max_terminals": host.max_terminals,
                            "allocated_terminals": host.allocated_terminals,
                        },
                    )
                chosen = host
            else:
                candidates = [
                    h
                    for h in self._hosts.values()
                    if not h.saturated and h.free_slots > 0
                ]
                if not candidates:
                    raise ConflictError(
                        "No worker host capacity available",
                        details={"hosts": len(self._hosts)},
                    )
                chosen = sorted(candidates, key=lambda h: (-h.free_slots, h.host_code))[
                    0
                ]
            updated = WorkerHostCapacity(
                host_id=chosen.host_id,
                host_code=chosen.host_code,
                max_terminals=chosen.max_terminals,
                allocated_terminals=chosen.allocated_terminals + 1,
                cpu_percent=chosen.cpu_percent,
                ram_percent=chosen.ram_percent,
                disk_percent=chosen.disk_percent,
                healthy=chosen.healthy,
                region=chosen.region,
                notes=chosen.notes,
                updated_at=datetime.now(UTC),
            )
            self._hosts[chosen.host_id] = updated
            return updated

    def release_slot(self, host_id: UUID) -> WorkerHostCapacity:
        with self._lock:
            host = self._hosts.get(host_id)
            if host is None:
                raise NotFoundError(
                    "Worker host not found", details={"host_id": str(host_id)}
                )
            allocated = max(0, host.allocated_terminals - 1)
            updated = WorkerHostCapacity(
                host_id=host.host_id,
                host_code=host.host_code,
                max_terminals=host.max_terminals,
                allocated_terminals=allocated,
                cpu_percent=host.cpu_percent,
                ram_percent=host.ram_percent,
                disk_percent=host.disk_percent,
                healthy=host.healthy,
                region=host.region,
                notes=host.notes,
                updated_at=datetime.now(UTC),
            )
            self._hosts[host_id] = updated
            return updated

    def summary(self) -> dict[str, object]:
        hosts = self.list_hosts()
        return {
            "host_count": len(hosts),
            "total_max_terminals": sum(h.max_terminals for h in hosts),
            "total_allocated": sum(h.allocated_terminals for h in hosts),
            "total_free": sum(h.free_slots for h in hosts),
            "healthy_hosts": sum(1 for h in hosts if h.healthy),
            "note": (
                "Capacity ledger only — does not prove real MT5 terminals are running"
            ),
        }
