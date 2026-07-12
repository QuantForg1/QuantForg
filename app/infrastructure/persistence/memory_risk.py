"""In-memory risk assessment persistence (tests + local runtime)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from app.domain.entities.risk_engine import RiskAssessment


class InMemoryRiskAssessmentRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, RiskAssessment] = {}

    async def add(self, assessment: RiskAssessment) -> RiskAssessment:
        self.items[assessment.id] = assessment
        return assessment

    async def get_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> RiskAssessment | None:
        key = request_id.strip()
        matches = [
            a
            for a in self.items.values()
            if a.user_id == user_id and a.request_id == key
        ]
        if not matches:
            return None
        return max(matches, key=lambda a: a.assessed_at)

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[RiskAssessment]:
        rows = [a for a in self.items.values() if a.user_id == user_id]
        rows.sort(key=lambda a: a.assessed_at, reverse=True)
        return rows[:limit]


class InMemoryRiskUnitOfWork:
    def __init__(self) -> None:
        self.assessments = InMemoryRiskAssessmentRepository()
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


class MemoryRiskUnitOfWorkFactory:
    def __init__(self) -> None:
        self._uow = InMemoryRiskUnitOfWork()

    def __call__(self) -> InMemoryRiskUnitOfWork:
        self._uow.committed = False
        self._uow.rolled_back = False
        return self._uow
