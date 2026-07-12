"""Operations Unit of Work ports — alerts, metrics, health history."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from app.domain.entities.ops import HealthHistoryEntry, SystemAlert, SystemMetricRecord


class SystemAlertRepositoryPort(Protocol):
    async def add(self, alert: SystemAlert) -> SystemAlert: ...

    async def get(self, alert_id: UUID) -> SystemAlert | None: ...

    async def list_open(self, *, limit: int = 100) -> list[SystemAlert]: ...

    async def list_recent(self, *, limit: int = 100) -> list[SystemAlert]: ...

    async def update(self, alert: SystemAlert) -> SystemAlert: ...

    async def find_open_by_code(self, code: str) -> SystemAlert | None: ...


class SystemMetricRepositoryPort(Protocol):
    async def add(self, record: SystemMetricRecord) -> SystemMetricRecord: ...

    async def list_recent(self, *, limit: int = 100) -> list[SystemMetricRecord]: ...


class HealthHistoryRepositoryPort(Protocol):
    async def add(self, entry: HealthHistoryEntry) -> HealthHistoryEntry: ...

    async def list_recent(self, *, limit: int = 100) -> list[HealthHistoryEntry]: ...


class OpsUnitOfWorkPort(Protocol):
    alerts: SystemAlertRepositoryPort
    metrics: SystemMetricRepositoryPort
    health_history: HealthHistoryRepositoryPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class OpsUnitOfWorkFactory(Protocol):
    def __call__(self) -> OpsUnitOfWorkPort: ...
