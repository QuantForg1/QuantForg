"""Paper Trading FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.paper_market_listener import PaperMarketListener
from app.application.services.paper_trading import PaperTradingEngine
from app.application.services.virtual_broker import VirtualBroker
from app.application.use_cases.paper import (
    GetPaperHistoryUseCase,
    GetPaperPerformanceUseCase,
    ListPaperPositionsUseCase,
    PlacePaperOrderUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.paper import PaperBrokerAssumptions
from app.infrastructure.brokers.mt5 import MT5Adapter
from core.di.container import get_container


def get_paper_uow_factory() -> Any:
    factory = getattr(get_container(), "paper_uow_factory", None)
    if factory is None:
        msg = "Paper Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_mt5_uow_factory() -> Any:
    factory = getattr(get_container(), "mt5_uow_factory", None)
    if factory is None:
        msg = "MT5 Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory


def get_mt5_adapter() -> MT5Adapter | None:
    return getattr(get_container(), "mt5_adapter", None)


def get_market_data() -> MT5MarketDataService | None:
    return getattr(get_container(), "mt5_market_data", None)


def get_paper_engine() -> PaperTradingEngine:
    engine = getattr(get_container(), "paper_trading_engine", None)
    if engine is not None:
        return engine  # type: ignore[no-any-return]
    market = get_market_data()
    if market is None:
        msg = "MT5 market data is not available for paper trading"
        raise RuntimeError(msg)
    return PaperTradingEngine(
        market_listener=PaperMarketListener(market_data=market),
        broker=VirtualBroker(assumptions=PaperBrokerAssumptions()),
    )


def get_place_paper_order() -> PlacePaperOrderUseCase:
    broker_uow = getattr(get_container(), "broker_uow_factory", None)
    if broker_uow is None:
        msg = "Broker Unit of Work factory is not available for audit"
        raise RuntimeError(msg)
    return PlacePaperOrderUseCase(
        paper_uow_factory=get_paper_uow_factory(),
        mt5_uow_factory=get_mt5_uow_factory(),
        engine=get_paper_engine(),
        mt5_adapter=get_mt5_adapter(),
        audit=RecordAuditEventUseCase(uow_factory=broker_uow),
    )


def get_list_paper_positions() -> ListPaperPositionsUseCase:
    return ListPaperPositionsUseCase(
        paper_uow_factory=get_paper_uow_factory(),
        engine=get_paper_engine(),
        mt5_adapter=get_mt5_adapter(),
    )


def get_paper_history() -> GetPaperHistoryUseCase:
    return GetPaperHistoryUseCase(paper_uow_factory=get_paper_uow_factory())


def get_paper_performance() -> GetPaperPerformanceUseCase:
    return GetPaperPerformanceUseCase(
        paper_uow_factory=get_paper_uow_factory(),
        engine=get_paper_engine(),
        mt5_adapter=get_mt5_adapter(),
    )


PlacePaperOrderDep = Annotated[PlacePaperOrderUseCase, Depends(get_place_paper_order)]
ListPaperPositionsDep = Annotated[
    ListPaperPositionsUseCase, Depends(get_list_paper_positions)
]
PaperHistoryDep = Annotated[GetPaperHistoryUseCase, Depends(get_paper_history)]
PaperPerformanceDep = Annotated[
    GetPaperPerformanceUseCase, Depends(get_paper_performance)
]
