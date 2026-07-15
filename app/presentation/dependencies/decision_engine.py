"""FastAPI dependencies for Decision Engine."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.application.services.decision_engine import DecisionEngineService
from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.use_cases.mt5 import GetMT5StatusUseCase
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.presentation.dependencies.intelligence import (
    get_market_context_engine,
    get_news_intelligence,
    get_provider_registry,
)
from app.presentation.dependencies.mt5 import get_mt5_adapter, get_mt5_uow_factory
from core.config.settings import Settings, get_settings


def get_decision_engine(
    settings: Annotated[Settings, Depends(get_settings)],
    adapter: Annotated[MT5Adapter, Depends(get_mt5_adapter)],
    uow_factory: Annotated[Any, Depends(get_mt5_uow_factory)],
) -> DecisionEngineService:
    registry = get_provider_registry(settings, adapter)
    return DecisionEngineService(
        status=GetMT5StatusUseCase(uow_factory=uow_factory, adapter=adapter),
        market_data=MT5MarketDataService(adapter=adapter),
        portfolio_sync=PortfolioSyncService(adapter=adapter),
        market_context=get_market_context_engine(),
        news=get_news_intelligence(registry),
    )


DecisionEngineSvc = Annotated[DecisionEngineService, Depends(get_decision_engine)]
