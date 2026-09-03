"""Portfolio sync use cases — read-only, never order_send."""

from __future__ import annotations

import asyncio
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
from app.application.services.mt5_session_guard import require_live_mt5_connection
from app.application.services.portfolio_sync import PortfolioSyncService
from app.domain.exceptions.base import NotFoundError


async def _require_active_connection(
    uow_factory: Any, sync_service: PortfolioSyncService, user_id: UUID
) -> None:
    await require_live_mt5_connection(uow_factory, sync_service.adapter, user_id)


@dataclass(frozen=True, slots=True)
class GetPortfolioUseCase:
    mt5_uow_factory: Any
    portfolio_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(self, *, user_id: UUID) -> PortfolioDTO:
        await _require_active_connection(
            self.mt5_uow_factory, self.sync_service, user_id
        )
        record = await asyncio.to_thread(
            self.sync_service.synchronize, user_id=user_id
        )
        _ = self.sync_service.drain_events()
        async with self.portfolio_uow_factory() as uow:
            await uow.syncs.add(record)
            await uow.commit()

        def _fresh_snapshot() -> tuple[Any, ...]:
            # Positions must bypass cycle/TTL pin — deals are always live.
            adapter = self.sync_service.adapter
            refresh = getattr(adapter, "force_refresh_positions", None)
            positions = (
                refresh()
                if callable(refresh)
                else self.sync_service.list_positions()
            )
            return (
                positions,
                self.sync_service.list_orders(),
                self.sync_service.history_orders(),
                self.sync_service.history_deals(),
                self.sync_service.account_snapshot(),
            )

        positions_raw, pending_raw, hist_orders_raw, hist_deals_raw, account_raw = (
            await asyncio.to_thread(_fresh_snapshot)
        )
        positions = [PositionDTO.from_entity(p) for p in positions_raw]
        pending = [PendingOrderDTO.from_entity(o) for o in pending_raw]
        hist_orders = [HistoryOrderDTO.from_entity(o) for o in hist_orders_raw]
        hist_deals = [DealDTO.from_entity(d) for d in hist_deals_raw]
        return PortfolioDTO(
            sync_id=record.id,
            account=AccountSnapshotDTO.from_entity(account_raw),
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
        await _require_active_connection(
            self.mt5_uow_factory, self.sync_service, user_id
        )
        adapter = self.sync_service.adapter
        if symbol:
            refresh = getattr(adapter, "force_refresh_positions", None)
            if callable(refresh):
                await asyncio.to_thread(refresh)
            rows = await asyncio.to_thread(
                self.sync_service.position_by_symbol, symbol
            )
        else:
            refresh = getattr(adapter, "force_refresh_positions", None)
            rows = await asyncio.to_thread(
                refresh if callable(refresh) else self.sync_service.list_positions
            )
        return [PositionDTO.from_entity(p) for p in rows]


@dataclass(frozen=True, slots=True)
class GetPositionByTicketUseCase:
    mt5_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(self, *, user_id: UUID, ticket: int) -> PositionDTO:
        await _require_active_connection(
            self.mt5_uow_factory, self.sync_service, user_id
        )
        adapter = self.sync_service.adapter
        refresh = getattr(adapter, "force_refresh_positions", None)
        if callable(refresh):
            await asyncio.to_thread(refresh)
        pos = await asyncio.to_thread(self.sync_service.position_by_ticket, ticket)
        if pos is None:
            raise NotFoundError(f"Position ticket {ticket} not found")
        return PositionDTO.from_entity(pos)


@dataclass(frozen=True, slots=True)
class ListOrdersUseCase:
    mt5_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(self, *, user_id: UUID) -> list[PendingOrderDTO]:
        await _require_active_connection(
            self.mt5_uow_factory, self.sync_service, user_id
        )
        orders = await asyncio.to_thread(self.sync_service.list_orders)
        return [PendingOrderDTO.from_entity(o) for o in orders]


@dataclass(frozen=True, slots=True)
class GetOrderByTicketUseCase:
    mt5_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(self, *, user_id: UUID, ticket: int) -> PendingOrderDTO:
        await _require_active_connection(
            self.mt5_uow_factory, self.sync_service, user_id
        )
        order = await asyncio.to_thread(self.sync_service.order_by_ticket, ticket)
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
        await _require_active_connection(
            self.mt5_uow_factory, self.sync_service, user_id
        )
        orders = await asyncio.to_thread(
            self.sync_service.history_orders, date_from=date_from, date_to=date_to
        )
        deals = await asyncio.to_thread(
            self.sync_service.history_deals, date_from=date_from, date_to=date_to
        )
        return HistoryDTO(
            orders=[HistoryOrderDTO.from_entity(o) for o in orders],
            deals=[DealDTO.from_entity(d) for d in deals],
        )


@dataclass(frozen=True, slots=True)
class GetAccountSnapshotUseCase:
    mt5_uow_factory: Any
    sync_service: PortfolioSyncService

    async def execute(self, *, user_id: UUID) -> AccountSnapshotDTO:
        await _require_active_connection(
            self.mt5_uow_factory, self.sync_service, user_id
        )
        snap = await asyncio.to_thread(self.sync_service.account_snapshot)
        return AccountSnapshotDTO.from_entity(snap)
