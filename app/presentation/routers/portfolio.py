"""Portfolio & Position Engine API — read-only synchronization."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.application.dto.portfolio import (
    AccountSnapshotDTO,
    DealDTO,
    HistoryOrderDTO,
    PendingOrderDTO,
    PositionDTO,
)
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.portfolio import (
    HistoryDep,
    OrdersDep,
    OrderTicketDep,
    PortfolioDep,
    PositionsDep,
    PositionTicketDep,
)
from app.presentation.dto_mapping import dto_to_dict
from app.presentation.schemas.portfolio import (
    AccountSnapshotResponse,
    DealResponse,
    HistoryOrderResponse,
    HistoryResponse,
    PendingOrderResponse,
    PortfolioResponse,
    PositionResponse,
)

router = APIRouter(tags=["portfolio"])


def _account(dto: AccountSnapshotDTO) -> AccountSnapshotResponse:
    return AccountSnapshotResponse(**dto_to_dict(dto))


def _position(dto: PositionDTO) -> PositionResponse:
    return PositionResponse(**dto_to_dict(dto))


def _pending(dto: PendingOrderDTO) -> PendingOrderResponse:
    return PendingOrderResponse(**dto_to_dict(dto))


def _hist_order(dto: HistoryOrderDTO) -> HistoryOrderResponse:
    return HistoryOrderResponse(**dto_to_dict(dto))


def _deal(dto: DealDTO) -> DealResponse:
    return DealResponse(**dto_to_dict(dto))


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    user: CurrentUser,
    portfolio: PortfolioDep,
) -> PortfolioResponse:
    """Synchronize and return full portfolio snapshot (read-only)."""
    dto = await portfolio.execute(user_id=user.id)
    return PortfolioResponse(
        sync_id=dto.sync_id,
        account=_account(dto.account),
        positions=[_position(p) for p in dto.positions],
        pending_orders=[_pending(o) for o in dto.pending_orders],
        history_orders=[_hist_order(o) for o in dto.history_orders],
        history_deals=[_deal(d) for d in dto.history_deals],
        synced_at=dto.synced_at,
        position_count=dto.position_count,
        pending_order_count=dto.pending_order_count,
    )


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(
    user: CurrentUser,
    positions: PositionsDep,
    symbol: str | None = Query(default=None),
) -> list[PositionResponse]:
    items = await positions.execute(user_id=user.id, symbol=symbol)
    return [_position(i) for i in items]


@router.get("/positions/{ticket}", response_model=PositionResponse)
async def get_position(
    ticket: int,
    user: CurrentUser,
    by_ticket: PositionTicketDep,
) -> PositionResponse:
    dto = await by_ticket.execute(user_id=user.id, ticket=ticket)
    return _position(dto)


@router.get("/orders", response_model=list[PendingOrderResponse])
async def list_orders(
    user: CurrentUser,
    orders: OrdersDep,
) -> list[PendingOrderResponse]:
    items = await orders.execute(user_id=user.id)
    return [_pending(i) for i in items]


@router.get("/orders/{ticket}", response_model=PendingOrderResponse)
async def get_order(
    ticket: int,
    user: CurrentUser,
    by_ticket: OrderTicketDep,
) -> PendingOrderResponse:
    dto = await by_ticket.execute(user_id=user.id, ticket=ticket)
    return _pending(dto)


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    user: CurrentUser,
    history: HistoryDep,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> HistoryResponse:
    dto = await history.execute(user_id=user.id, date_from=date_from, date_to=date_to)
    return HistoryResponse(
        orders=[_hist_order(o) for o in dto.orders],
        deals=[_deal(d) for d in dto.deals],
    )
