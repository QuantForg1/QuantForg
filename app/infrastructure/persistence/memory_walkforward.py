"""In-memory Walk-Forward persistence (tests + local runtime)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from app.domain.entities.walkforward import WalkForwardRun


class InMemoryWalkForwardRunRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, WalkForwardRun] = {}

    async def add(self, run: WalkForwardRun) -> WalkForwardRun:
        self.items[run.id] = run
        return run

    async def get(self, run_id: UUID) -> WalkForwardRun | None:
        return self.items.get(run_id)

    async def get_for_user(self, user_id: UUID, run_id: UUID) -> WalkForwardRun | None:
        run = self.items.get(run_id)
        if run is None or run.user_id != user_id:
            return None
        return run

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[WalkForwardRun]:
        rows = [r for r in self.items.values() if r.user_id == user_id]
        rows.sort(key=lambda r: r.created_at, reverse=True)
        return rows[:limit]


class InMemoryWalkForwardUnitOfWork:
    def __init__(self) -> None:
        self.runs = InMemoryWalkForwardRunRepository()
        self.oos_metrics: list[dict[str, object]] = []
        self.robustness_reports: list[dict[str, object]] = []
        self.committed = False
        self.rolled_back = False

    async def add_oos_metrics(
        self, *, user_id: UUID, run_id: UUID, payload: dict[str, object]
    ) -> None:
        self.oos_metrics.append(
            {"user_id": user_id, "run_id": run_id, "payload": dict(payload)}
        )

    async def add_robustness_report(
        self, *, user_id: UUID, run_id: UUID, payload: dict[str, object]
    ) -> None:
        self.robustness_reports.append(
            {"user_id": user_id, "run_id": run_id, "payload": dict(payload)}
        )

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


class MemoryWalkForwardUnitOfWorkFactory:
    def __init__(self) -> None:
        self._uow = InMemoryWalkForwardUnitOfWork()

    def __call__(self) -> InMemoryWalkForwardUnitOfWork:
        self._uow.committed = False
        self._uow.rolled_back = False
        return self._uow
