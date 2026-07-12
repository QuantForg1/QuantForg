"""FastAPI dependencies for MT5 connection, market-data, and order validation."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.application.services.mt5_service import MT5Service
from app.application.use_cases.mt5 import (
    ConnectMT5UseCase,
    DisconnectMT5UseCase,
    GetMT5AccountUseCase,
    GetMT5CandlesUseCase,
    GetMT5StatusUseCase,
    GetMT5SymbolUseCase,
    GetMT5TickUseCase,
    ListMT5SymbolsUseCase,
)
from app.application.use_cases.mt5_order import (
    CalculateMT5OrderUseCase,
    ValidateMT5OrderUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
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


def get_mt5_market_data() -> MT5MarketDataService:
    service = getattr(get_container(), "mt5_market_data", None)
    if service is None:
        return MT5MarketDataService(adapter=get_mt5_adapter())
    return service  # type: ignore[no-any-return]


def get_mt5_order_validation() -> MT5OrderValidationService:
    service = getattr(get_container(), "mt5_order_validation", None)
    if service is None:
        return MT5OrderValidationService(adapter=get_mt5_adapter())
    return service  # type: ignore[no-any-return]


def get_mt5_service() -> MT5Service:
    adapter = get_mt5_adapter()
    uow_factory = get_mt5_uow_factory()
    market_data = get_mt5_market_data()
    order_validation = get_mt5_order_validation()
    broker_uow = getattr(get_container(), "broker_uow_factory", None)
    if broker_uow is None:
        msg = "Broker Unit of Work factory is not available for audit"
        raise RuntimeError(msg)
    audit = RecordAuditEventUseCase(uow_factory=broker_uow)
    return MT5Service(
        get_status=GetMT5StatusUseCase(uow_factory=uow_factory, adapter=adapter),
        connect=ConnectMT5UseCase(
            uow_factory=uow_factory, adapter=adapter, audit=audit
        ),
        disconnect=DisconnectMT5UseCase(
            uow_factory=uow_factory, adapter=adapter, audit=audit
        ),
        get_account=GetMT5AccountUseCase(uow_factory=uow_factory, adapter=adapter),
        list_symbols=ListMT5SymbolsUseCase(uow_factory=uow_factory, adapter=adapter),
        get_symbol=GetMT5SymbolUseCase(
            uow_factory=uow_factory, market_data=market_data
        ),
        get_tick=GetMT5TickUseCase(uow_factory=uow_factory, market_data=market_data),
        get_candles=GetMT5CandlesUseCase(
            uow_factory=uow_factory, market_data=market_data
        ),
        market_data=market_data,
        order_validation=order_validation,
        validate_order=ValidateMT5OrderUseCase(
            uow_factory=uow_factory,
            validation_service=order_validation,
            audit=audit,
        ),
        calculate_order=CalculateMT5OrderUseCase(
            uow_factory=uow_factory,
            validation_service=order_validation,
        ),
    )


MT5Svc = Annotated[MT5Service, Depends(get_mt5_service)]
