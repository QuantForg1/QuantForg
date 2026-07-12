"""In-memory Backtest persistence (tests + local runtime)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from app.domain.entities.backtest import BacktestRun, SimulatedTrade


class InMemoryBacktestRunRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, BacktestRun] = {}

    async def add(self, run: BacktestRun) -> BacktestRun:
        self.items[run.id] = run
        return run

    async def get(self, backtest_id: UUID) -> BacktestRun | None:
        return self.items.get(backtest_id)

    async def get_for_user(
        self, user_id: UUID, backtest_id: UUID
    ) -> BacktestRun | None:
        run = self.items.get(backtest_id)
        if run is None or run.user_id != user_id:
            return None
        return run

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[BacktestRun]:
        rows = [r for r in self.items.values() if r.user_id == user_id]
        rows.sort(key=lambda r: r.created_at, reverse=True)
        return rows[:limit]


class InMemorySimulatedTradeRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, SimulatedTrade] = {}

    async def add(self, trade: SimulatedTrade) -> SimulatedTrade:
        self.items[trade.id] = trade
        return trade

    async def list_for_backtest(
        self, backtest_id: UUID, *, limit: int = 500
    ) -> list[SimulatedTrade]:
        rows = [t for t in self.items.values() if t.backtest_id == backtest_id]
        rows.sort(key=lambda t: t.opened_at)
        return rows[:limit]


class InMemoryBacktestUnitOfWork:
    def __init__(self) -> None:
        self.runs = InMemoryBacktestRunRepository()
        self.trades = InMemorySimulatedTradeRepository()
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


class MemoryBacktestUnitOfWorkFactory:
    def __init__(self) -> None:
        self._uow = InMemoryBacktestUnitOfWork()

    def __call__(self) -> InMemoryBacktestUnitOfWork:
        self._uow.committed = False
        self._uow.rolled_back = False
        return self._uow
