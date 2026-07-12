"""In-memory Paper Trading persistence (tests + local runtime)."""

from __future__ import annotations

from decimal import Decimal
from typing import Self
from uuid import UUID

from app.domain.entities.paper import (
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
)
from app.domain.enums.paper import PaperOrderStatus, PaperPositionStatus


class InMemoryPaperPortfolioRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, PaperPortfolio] = {}

    async def get(self, user_id: UUID) -> PaperPortfolio | None:
        return self.items.get(user_id)

    async def save(self, portfolio: PaperPortfolio) -> PaperPortfolio:
        self.items[portfolio.user_id] = portfolio
        return portfolio


class InMemoryPaperOrderRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, PaperOrder] = {}

    async def add(self, order: PaperOrder) -> PaperOrder:
        self.items[order.id] = order
        return order

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 100
    ) -> list[PaperOrder]:
        rows = [o for o in self.items.values() if o.user_id == user_id]
        rows.sort(key=lambda o: o.submitted_at, reverse=True)
        return rows[:limit]

    async def list_pending(self, user_id: UUID) -> list[PaperOrder]:
        return [
            o
            for o in self.items.values()
            if o.user_id == user_id and o.status is PaperOrderStatus.ACCEPTED
        ]


class InMemoryPaperPositionRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, PaperPosition] = {}

    async def add(self, position: PaperPosition) -> PaperPosition:
        self.items[position.id] = position
        return position

    async def save(self, position: PaperPosition) -> PaperPosition:
        self.items[position.id] = position
        return position

    async def get(self, position_id: UUID) -> PaperPosition | None:
        return self.items.get(position_id)

    async def list_open(self, user_id: UUID) -> list[PaperPosition]:
        return [
            p
            for p in self.items.values()
            if p.user_id == user_id
            and p.status
            in {PaperPositionStatus.OPENED, PaperPositionStatus.PARTIALLY_CLOSED}
        ]

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 100
    ) -> list[PaperPosition]:
        rows = [p for p in self.items.values() if p.user_id == user_id]
        rows.sort(key=lambda p: p.opened_at, reverse=True)
        return rows[:limit]


class InMemoryPaperTradeRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, PaperTrade] = {}

    async def add(self, trade: PaperTrade) -> PaperTrade:
        self.items[trade.id] = trade
        return trade

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 100
    ) -> list[PaperTrade]:
        rows = [t for t in self.items.values() if t.user_id == user_id]
        rows.sort(key=lambda t: t.closed_at, reverse=True)
        return rows[:limit]


class InMemoryPaperPerformanceRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, dict[str, object]] = {}

    async def save(self, user_id: UUID, payload: dict[str, object]) -> None:
        self.items[user_id] = dict(payload)

    async def get(self, user_id: UUID) -> dict[str, object] | None:
        return self.items.get(user_id)


class InMemoryPaperUnitOfWork:
    def __init__(self) -> None:
        self.portfolios = InMemoryPaperPortfolioRepository()
        self.orders = InMemoryPaperOrderRepository()
        self.positions = InMemoryPaperPositionRepository()
        self.trades = InMemoryPaperTradeRepository()
        self.performance = InMemoryPaperPerformanceRepository()
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


class MemoryPaperUnitOfWorkFactory:
    def __init__(self) -> None:
        self._uow = InMemoryPaperUnitOfWork()

    def __call__(self) -> InMemoryPaperUnitOfWork:
        self._uow.committed = False
        self._uow.rolled_back = False
        return self._uow


def portfolio_from_dict(user_id: UUID, data: dict[str, object]) -> PaperPortfolio:
    """Helper for reconstructing portfolio from persisted snapshot."""
    return PaperPortfolio(
        user_id=user_id,
        initial_balance=Decimal(str(data.get("initial_balance", "10000"))),
        balance=Decimal(str(data.get("balance", "10000"))),
        equity=Decimal(str(data.get("equity", "10000"))),
        floating_pnl=Decimal(str(data.get("floating_pnl", "0"))),
        realized_pnl=Decimal(str(data.get("realized_pnl", "0"))),
        margin=Decimal(str(data.get("margin", "0"))),
        peak_equity=Decimal(str(data.get("peak_equity", data.get("equity", "10000")))),
        max_drawdown_pct=Decimal(str(data.get("max_drawdown_pct", "0"))),
    )
