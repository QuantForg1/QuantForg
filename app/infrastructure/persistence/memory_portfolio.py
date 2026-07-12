"""In-memory portfolio sync persistence (tests + local runtime)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from app.domain.entities.mt5_portfolio import PortfolioSyncRecord


class InMemoryPortfolioSyncRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, PortfolioSyncRecord] = {}

    async def add(self, record: PortfolioSyncRecord) -> PortfolioSyncRecord:
        self.items[record.id] = record
        return record

    async def get_latest_for_user(self, user_id: UUID) -> PortfolioSyncRecord | None:
        rows = [r for r in self.items.values() if r.user_id == user_id]
        if not rows:
            return None
        return max(rows, key=lambda r: r.synced_at)

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 20
    ) -> list[PortfolioSyncRecord]:
        rows = [r for r in self.items.values() if r.user_id == user_id]
        rows.sort(key=lambda r: r.synced_at, reverse=True)
        return rows[:limit]


class InMemoryPortfolioUnitOfWork:
    def __init__(self) -> None:
        self.syncs = InMemoryPortfolioSyncRepository()
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


class MemoryPortfolioUnitOfWorkFactory:
    def __init__(self) -> None:
        self._uow = InMemoryPortfolioUnitOfWork()

    def __call__(self) -> InMemoryPortfolioUnitOfWork:
        self._uow.committed = False
        self._uow.rolled_back = False
        return self._uow
