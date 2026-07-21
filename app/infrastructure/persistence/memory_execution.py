"""In-memory execution safety + gateway persistence (tests + local runtime)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from app.domain.entities.execution_gateway import ExecutionAttempt
from app.domain.entities.execution_safety import ExecutionDecisionRecord


class InMemoryExecutionDecisionRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, ExecutionDecisionRecord] = {}

    async def add(self, decision: ExecutionDecisionRecord) -> ExecutionDecisionRecord:
        self.items[decision.id] = decision
        return decision

    async def get_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> ExecutionDecisionRecord | None:
        key = request_id.strip()
        matches = [
            d
            for d in self.items.values()
            if d.user_id == user_id and d.request_id == key and not d.idempotent_replay
        ]
        if not matches:
            matches = [
                d
                for d in self.items.values()
                if d.user_id == user_id and d.request_id == key
            ]
        if not matches:
            return None
        return max(matches, key=lambda d: d.decided_at)

    async def list_recent_for_user(
        self, user_id: UUID, *, limit: int = 100
    ) -> list[ExecutionDecisionRecord]:
        rows = [d for d in self.items.values() if d.user_id == user_id]
        rows.sort(key=lambda d: d.decided_at, reverse=True)
        return rows[:limit]


class InMemoryExecutionAttemptRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, ExecutionAttempt] = {}

    async def add(self, attempt: ExecutionAttempt) -> ExecutionAttempt:
        # Enforce one non-replay row per (user_id, request_id) — reserve-before-send.
        if not attempt.idempotent_replay:
            doomed = [
                key
                for key, row in self.items.items()
                if row.user_id == attempt.user_id
                and row.request_id == attempt.request_id
                and not row.idempotent_replay
                and key != attempt.id
            ]
            for key in doomed:
                del self.items[key]
        self.items[attempt.id] = attempt
        return attempt

    async def get_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> ExecutionAttempt | None:
        key = request_id.strip()
        matches = [
            a
            for a in self.items.values()
            if a.user_id == user_id and a.request_id == key and not a.idempotent_replay
        ]
        if not matches:
            matches = [
                a
                for a in self.items.values()
                if a.user_id == user_id and a.request_id == key
            ]
        if not matches:
            return None
        return max(matches, key=lambda a: a.submitted_at)

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[ExecutionAttempt]:
        rows = [a for a in self.items.values() if a.user_id == user_id]
        rows.sort(key=lambda a: a.submitted_at, reverse=True)
        return rows[:limit]


class InMemoryExecutionUnitOfWork:
    def __init__(self) -> None:
        self.decisions = InMemoryExecutionDecisionRepository()
        self.attempts = InMemoryExecutionAttemptRepository()
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


class MemoryExecutionUnitOfWorkFactory:
    """Shared in-memory store; each call returns a UoW over the same repos."""

    def __init__(self) -> None:
        self._uow = InMemoryExecutionUnitOfWork()

    def __call__(self) -> InMemoryExecutionUnitOfWork:
        self._uow.committed = False
        self._uow.rolled_back = False
        return self._uow
