"""Portfolio FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.use_cases.portfolio import (
    GetHistoryUseCase,
    GetOrderByTicketUseCase,
    GetPortfolioUseCase,
    GetPositionByTicketUseCase,
    ListOrdersUseCase,
    ListPositionsUseCase,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from core.di.container import get_container


def get_mt5_adapter() -> MT5Adapter:
    adapter = getattr(get_container(), "mt5_adapter", None)
    if adapter is None:
        msg = "MT5 adapter is not available"
        raise RuntimeError(msg)
    return adapter  # type: ignore[no-any-return]


def get_mt5_uow_factory() -> Any:
    factory = getattr(get_container(), "mt5_uow_factory", None)
    if factory is None:
        msg = "MT5 Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_portfolio_uow_factory() -> Any:
    factory = getattr(get_container(), "portfolio_uow_factory", None)
    if factory is None:
        msg = "Portfolio Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_portfolio_sync_service() -> PortfolioSyncService:
    service = getattr(get_container(), "portfolio_sync", None)
    if service is not None:
        return service  # type: ignore[no-any-return]
    return PortfolioSyncService(adapter=get_mt5_adapter())


def get_portfolio_use_case() -> GetPortfolioUseCase:
    return GetPortfolioUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        portfolio_uow_factory=get_portfolio_uow_factory(),
        sync_service=get_portfolio_sync_service(),
    )


def get_list_positions() -> ListPositionsUseCase:
    return ListPositionsUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        sync_service=get_portfolio_sync_service(),
    )


def get_position_by_ticket() -> GetPositionByTicketUseCase:
    return GetPositionByTicketUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        sync_service=get_portfolio_sync_service(),
    )


def get_list_orders() -> ListOrdersUseCase:
    return ListOrdersUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        sync_service=get_portfolio_sync_service(),
    )


def get_order_by_ticket() -> GetOrderByTicketUseCase:
    return GetOrderByTicketUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        sync_service=get_portfolio_sync_service(),
    )


def get_history() -> GetHistoryUseCase:
    return GetHistoryUseCase(
        mt5_uow_factory=get_mt5_uow_factory(),
        sync_service=get_portfolio_sync_service(),
    )


PortfolioDep = Annotated[GetPortfolioUseCase, Depends(get_portfolio_use_case)]
PositionsDep = Annotated[ListPositionsUseCase, Depends(get_list_positions)]
PositionTicketDep = Annotated[
    GetPositionByTicketUseCase, Depends(get_position_by_ticket)
]
OrdersDep = Annotated[ListOrdersUseCase, Depends(get_list_orders)]
OrderTicketDep = Annotated[GetOrderByTicketUseCase, Depends(get_order_by_ticket)]
HistoryDep = Annotated[GetHistoryUseCase, Depends(get_history)]
