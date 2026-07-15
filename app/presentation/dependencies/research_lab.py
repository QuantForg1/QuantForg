"""FastAPI dependencies for Quant Research Lab (analysis-only)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.research_lab import ResearchLabService
from app.application.use_cases.mt5 import GetMT5StatusUseCase
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.presentation.dependencies.intelligence import get_market_context_engine
from app.presentation.dependencies.mt5 import get_mt5_adapter, get_mt5_uow_factory


def get_research_lab(
    adapter: Annotated[MT5Adapter, Depends(get_mt5_adapter)],
    uow_factory: Annotated[Any, Depends(get_mt5_uow_factory)],
) -> ResearchLabService:
    return ResearchLabService(
        status=GetMT5StatusUseCase(uow_factory=uow_factory, adapter=adapter),
        market_data=MT5MarketDataService(adapter=adapter),
        portfolio_sync=PortfolioSyncService(adapter=adapter),
        market_context=get_market_context_engine(),
    )


ResearchLabSvc = Annotated[ResearchLabService, Depends(get_research_lab)]
