"""In-memory execution audit persistence (tests + local runtime)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from app.domain.entities.execution_audit import ExecutionAudit


class InMemoryExecutionAuditRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, ExecutionAudit] = {}

    async def add(self, audit: ExecutionAudit) -> ExecutionAudit:
        self.items[audit.id] = audit
        return audit

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[ExecutionAudit]:
        rows = [a for a in self.items.values() if a.user_id == user_id]
        rows.sort(key=lambda a: a.created_at, reverse=True)
        return rows[: max(1, min(limit, 500))]

    async def list_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> list[ExecutionAudit]:
        key = request_id.strip()
        rows = [
            a
            for a in self.items.values()
            if a.user_id == user_id and a.request_id == key
        ]
        rows.sort(key=lambda a: a.created_at)
        return rows


class InMemoryExecutionAuditUnitOfWork:
    def __init__(self) -> None:
        self.audits = InMemoryExecutionAuditRepository()
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


class MemoryExecutionAuditUnitOfWorkFactory:
    """Shared in-memory store; each call returns a UoW over the same repos."""

    def __init__(self) -> None:
        self._uow = InMemoryExecutionAuditUnitOfWork()

    def __call__(self) -> InMemoryExecutionAuditUnitOfWork:
        self._uow.committed = False
        self._uow.rolled_back = False
        return self._uow
