"""In-memory Operations & Observability persistence."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from app.domain.entities.ops import HealthHistoryEntry, SystemAlert, SystemMetricRecord
from app.domain.enums.ops import AlertStatus


class InMemorySystemAlertRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, SystemAlert] = {}

    async def add(self, alert: SystemAlert) -> SystemAlert:
        self.items[alert.id] = alert
        return alert

    async def get(self, alert_id: object) -> SystemAlert | None:
        if not isinstance(alert_id, UUID):
            return None
        return self.items.get(alert_id)

    async def list_open(self, *, limit: int = 100) -> list[SystemAlert]:
        rows = [
            a
            for a in self.items.values()
            if a.status in {AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED}
        ]
        rows.sort(key=lambda a: a.triggered_at, reverse=True)
        return rows[:limit]

    async def list_recent(self, *, limit: int = 100) -> list[SystemAlert]:
        rows = list(self.items.values())
        rows.sort(key=lambda a: a.triggered_at, reverse=True)
        return rows[:limit]

    async def update(self, alert: SystemAlert) -> SystemAlert:
        self.items[alert.id] = alert
        return alert

    async def find_open_by_code(self, code: str) -> SystemAlert | None:
        key = code.strip().lower()
        for alert in self.items.values():
            if alert.code == key and alert.status in {
                AlertStatus.OPEN,
                AlertStatus.ACKNOWLEDGED,
            }:
                return alert
        return None


class InMemorySystemMetricRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, SystemMetricRecord] = {}

    async def add(self, record: SystemMetricRecord) -> SystemMetricRecord:
        self.items[record.id] = record
        return record

    async def list_recent(self, *, limit: int = 100) -> list[SystemMetricRecord]:
        rows = list(self.items.values())
        rows.sort(key=lambda r: r.recorded_at, reverse=True)
        return rows[:limit]


class InMemoryHealthHistoryRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, HealthHistoryEntry] = {}

    async def add(self, entry: HealthHistoryEntry) -> HealthHistoryEntry:
        self.items[entry.id] = entry
        return entry

    async def list_recent(self, *, limit: int = 100) -> list[HealthHistoryEntry]:
        rows = list(self.items.values())
        rows.sort(key=lambda e: e.recorded_at, reverse=True)
        return rows[:limit]


class InMemoryOpsUnitOfWork:
    def __init__(self) -> None:
        self.alerts = InMemorySystemAlertRepository()
        self.metrics = InMemorySystemMetricRepository()
        self.health_history = InMemoryHealthHistoryRepository()
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self) -> Self:
        self.committed = False
        self.rolled_back = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        if exc_type is not None and not self.rolled_back:
            await self.rollback()


class MemoryOpsUnitOfWorkFactory:
    def __init__(self) -> None:
        self._uow = InMemoryOpsUnitOfWork()

    def __call__(self) -> InMemoryOpsUnitOfWork:
        self._uow.committed = False
        self._uow.rolled_back = False
        return self._uow
