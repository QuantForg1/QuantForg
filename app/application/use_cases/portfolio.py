"""Portfolio sync use cases — read-only, never order_send."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.application.dto.portfolio import (
    AccountSnapshotDTO,
    DealDTO,
    HistoryDTO,
    HistoryOrderDTO,
    PendingOrderDTO,
    PortfolioDTO,
    PositionDTO,
)
from app.application.services.portfolio_sync import PortfolioSyncService
from app.domain.exceptions.base import NotFoundError


async def _require_active_connection(uow_factory: Any, user_id: UUID) -> None:
    async with uow_factory() as uow:
        connection = await uow.connections.get_active_for_user(user_id)
    if connection is None or not connection.connected:
        raise NotFoundError("No active MT5 connection")


@dataclass(frozen=True, slots=True)
class GetPortfolioUseCase:
    mt5_uow_factory: Any
    portfolio_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(self, *, user_id: UUID) -> PortfolioDTO:
        await _require_active_connection(self.mt5_uow_factory, user_id)
        record = self.sync_service.synchronize(user_id=user_id)
        _ = self.sync_service.drain_events()
        async with self.portfolio_uow_factory() as uow:
            await uow.syncs.add(record)
            await uow.commit()
        positions = [
            PositionDTO.from_entity(p) for p in self.sync_service.list_positions()
        ]
        pending = [
            PendingOrderDTO.from_entity(o) for o in self.sync_service.list_orders()
        ]
        hist_orders = [
            HistoryOrderDTO.from_entity(o) for o in self.sync_service.history_orders()
        ]
        hist_deals = [DealDTO.from_entity(d) for d in self.sync_service.history_deals()]
        return PortfolioDTO(
            sync_id=record.id,
            account=AccountSnapshotDTO.from_entity(
                self.sync_service.account_snapshot()
            ),
            positions=positions,
            pending_orders=pending,
            history_orders=hist_orders,
            history_deals=hist_deals,
            synced_at=record.synced_at,
            position_count=len(positions),
            pending_order_count=len(pending),
        )


@dataclass(frozen=True, slots=True)
class ListPositionsUseCase:
    mt5_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(
        self, *, user_id: UUID, symbol: str | None = None
    ) -> list[PositionDTO]:
        await _require_active_connection(self.mt5_uow_factory, user_id)
        if symbol:
            rows = self.sync_service.position_by_symbol(symbol)
        else:
            rows = self.sync_service.list_positions()
        return [PositionDTO.from_entity(p) for p in rows]


@dataclass(frozen=True, slots=True)
class GetPositionByTicketUseCase:
    mt5_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(self, *, user_id: UUID, ticket: int) -> PositionDTO:
        await _require_active_connection(self.mt5_uow_factory, user_id)
        pos = self.sync_service.position_by_ticket(ticket)
        if pos is None:
            raise NotFoundError(f"Position ticket {ticket} not found")
        return PositionDTO.from_entity(pos)


@dataclass(frozen=True, slots=True)
class ListOrdersUseCase:
    mt5_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(self, *, user_id: UUID) -> list[PendingOrderDTO]:
        await _require_active_connection(self.mt5_uow_factory, user_id)
        return [PendingOrderDTO.from_entity(o) for o in self.sync_service.list_orders()]


@dataclass(frozen=True, slots=True)
class GetOrderByTicketUseCase:
    mt5_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(self, *, user_id: UUID, ticket: int) -> PendingOrderDTO:
        await _require_active_connection(self.mt5_uow_factory, user_id)
        order = self.sync_service.order_by_ticket(ticket)
        if order is None:
            raise NotFoundError(f"Pending order ticket {ticket} not found")
        return PendingOrderDTO.from_entity(order)


@dataclass(frozen=True, slots=True)
class GetHistoryUseCase:
    mt5_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(
        self,
        *,
        user_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> HistoryDTO:
        await _require_active_connection(self.mt5_uow_factory, user_id)
        orders = self.sync_service.history_orders(date_from=date_from, date_to=date_to)
        deals = self.sync_service.history_deals(date_from=date_from, date_to=date_to)
        return HistoryDTO(
            orders=[HistoryOrderDTO.from_entity(o) for o in orders],
            deals=[DealDTO.from_entity(d) for d in deals],
        )


@dataclass(frozen=True, slots=True)
class GetAccountSnapshotUseCase:
    mt5_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(self, *, user_id: UUID) -> AccountSnapshotDTO:
        await _require_active_connection(self.mt5_uow_factory, user_id)
        return AccountSnapshotDTO.from_entity(self.sync_service.account_snapshot())
