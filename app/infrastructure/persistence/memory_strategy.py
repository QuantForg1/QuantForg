"""In-memory Strategy Runtime persistence (tests + local runtime)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from app.domain.entities.strategy_runtime import StrategyEvaluation, StrategySignal


class InMemoryStrategyEvaluationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, StrategyEvaluation] = {}

    async def add(self, evaluation: StrategyEvaluation) -> StrategyEvaluation:
        self.items[evaluation.id] = evaluation
        return evaluation

    async def get_by_request_id(
        self, user_id: UUID, request_id: str
    ) -> StrategyEvaluation | None:
        key = request_id.strip()
        matches = [
            e
            for e in self.items.values()
            if e.user_id == user_id and e.request_id == key
        ]
        if not matches:
            return None
        return max(matches, key=lambda e: e.evaluated_at)

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[StrategyEvaluation]:
        rows = [e for e in self.items.values() if e.user_id == user_id]
        rows.sort(key=lambda e: e.evaluated_at, reverse=True)
        return rows[:limit]


class InMemoryStrategySignalRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, StrategySignal] = {}

    async def add(self, signal: StrategySignal) -> StrategySignal:
        self.items[signal.id] = signal
        return signal

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50, include_rejected: bool = True
    ) -> list[StrategySignal]:
        rows = [s for s in self.items.values() if s.user_id == user_id]
        if not include_rejected:
            rows = [s for s in rows if not s.rejected]
        rows.sort(key=lambda s: s.generated_at, reverse=True)
        return rows[:limit]


class InMemoryStrategyDecisionHistoryRepository:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []

    async def add(
        self,
        *,
        user_id: UUID,
        evaluation_id: UUID,
        decision: str,
        reasons: list[str],
    ) -> None:
        self.items.append(
            {
                "user_id": user_id,
                "evaluation_id": evaluation_id,
                "decision": decision,
                "reasons": list(reasons),
            }
        )


class InMemoryStrategyUnitOfWork:
    def __init__(self) -> None:
        self.evaluations = InMemoryStrategyEvaluationRepository()
        self.signals = InMemoryStrategySignalRepository()
        self.decision_history = InMemoryStrategyDecisionHistoryRepository()
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


class MemoryStrategyUnitOfWorkFactory:
    def __init__(self) -> None:
        self._uow = InMemoryStrategyUnitOfWork()

    def __call__(self) -> InMemoryStrategyUnitOfWork:
        self._uow.committed = False
        self._uow.rolled_back = False
        return self._uow
