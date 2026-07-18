"""FastAPI dependencies for Market Intelligence."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends

from app.application.services.ai_market_advisor import AiMarketAdvisor
from app.application.services.market_intelligence import MarketIntelligenceService
from app.application.services.news_intelligence import NewsIntelligenceService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.provider_registry import IntelligenceProviderRegistry
from app.application.use_cases.mt5 import GetMT5StatusUseCase, ListMT5SymbolsUseCase
from app.domain.interfaces.news import EconomicEvent, NewsItem
from app.domain.market_context.engine import MarketContextEngine
from app.domain.market_context.liquidity_resolver import LiquidityProfileResolver
from app.domain.market_context.market_clock import MarketClock
from app.domain.market_context.session_resolver import SessionResolver
from app.domain.market_context.trading_calendar import TradingCalendarService
from app.domain.market_context.volatility_resolver import VolatilityProfileResolver
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.intelligence.factory import build_provider_registry
from app.infrastructure.market_context.default_fx_ports import (
    DefaultFxSessionPort,
    DefaultLiquidityProfilePort,
    DefaultVolatilityProfilePort,
    SystemClockPort,
    WeekendCalendarPort,
)
from app.presentation.dependencies.mt5 import get_mt5_adapter, get_mt5_uow_factory
from core.config.settings import Settings, get_settings


def get_market_context_engine() -> MarketContextEngine:
    clock = MarketClock(SystemClockPort())
    return MarketContextEngine(
        clock=clock,
        sessions=SessionResolver(sessions=DefaultFxSessionPort(), clock=clock),
        calendar=TradingCalendarService(
            calendar=WeekendCalendarPort(),
            clock=clock,
        ),
        liquidity=LiquidityProfileResolver(DefaultLiquidityProfilePort()),
        volatility=VolatilityProfileResolver(DefaultVolatilityProfilePort()),
    )


def get_provider_registry(
    settings: Annotated[Settings, Depends(get_settings)],
    adapter: Annotated[MT5Adapter, Depends(get_mt5_adapter)],
) -> IntelligenceProviderRegistry:
    return build_provider_registry(settings, mt5_adapter=adapter)


class _RegistryNewsFeed:
    def __init__(self, registry: IntelligenceProviderRegistry) -> None:
        self._registry = registry

    def list_news(self, *, limit: int = 20) -> list[NewsItem]:
        return [
            NewsItem(
                id=a.id,
                title=a.title,
                summary=a.summary,
                source=a.source,
                url=a.url,
                published_at=a.published_at,
                symbols=a.symbols,
            )
            for a in self._registry.list_news(limit=limit)
        ]


class _RegistryCalendar:
    def __init__(self, registry: IntelligenceProviderRegistry) -> None:
        self._registry = registry

    def list_events(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> list[EconomicEvent]:
        return [
            EconomicEvent(
                id=e.id,
                title=e.title,
                country=e.country,
                impact=e.impact,
                scheduled_at=e.scheduled_at,
                actual=e.actual,
                forecast=e.forecast,
                previous=e.previous,
                source=e.provider,
            )
            for e in self._registry.list_calendar(limit=limit, as_of=as_of)
        ]


def get_news_intelligence(
    registry: Annotated[IntelligenceProviderRegistry, Depends(get_provider_registry)],
) -> NewsIntelligenceService:
    return NewsIntelligenceService(
        news_feed=_RegistryNewsFeed(registry),
        calendar=_RegistryCalendar(registry),
    )


def get_market_intelligence(
    settings: Annotated[Settings, Depends(get_settings)],
    adapter: Annotated[MT5Adapter, Depends(get_mt5_adapter)],
    uow_factory: Annotated[Any, Depends(get_mt5_uow_factory)],
    registry: Annotated[IntelligenceProviderRegistry, Depends(get_provider_registry)],
) -> MarketIntelligenceService:
    _ = settings
    return MarketIntelligenceService(
        status=GetMT5StatusUseCase(uow_factory=uow_factory, adapter=adapter),
        symbols=ListMT5SymbolsUseCase(uow_factory=uow_factory, adapter=adapter),
        portfolio_sync=PortfolioSyncService(adapter=adapter),
        market_context=get_market_context_engine(),
        news=get_news_intelligence(registry),
        advisor=AiMarketAdvisor(),
    )


MarketIntelSvc = Annotated[MarketIntelligenceService, Depends(get_market_intelligence)]
NewsIntelSvc = Annotated[NewsIntelligenceService, Depends(get_news_intelligence)]
ProviderRegistrySvc = Annotated[
    IntelligenceProviderRegistry, Depends(get_provider_registry)
]
