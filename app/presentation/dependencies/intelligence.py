"""FastAPI dependencies for Market Intelligence."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends

from app.application.services.ai_market_advisor import AiMarketAdvisor
from app.application.services.market_intelligence import MarketIntelligenceService
from app.application.services.news_intelligence import NewsIntelligenceService
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.use_cases.mt5 import GetMT5StatusUseCase, ListMT5SymbolsUseCase
from app.domain.market_context.engine import MarketContextEngine
from app.domain.market_context.liquidity_resolver import LiquidityProfileResolver
from app.domain.market_context.market_clock import MarketClock
from app.domain.market_context.session_resolver import SessionResolver
from app.domain.market_context.trading_calendar import TradingCalendarService
from app.domain.market_context.volatility_resolver import VolatilityProfileResolver
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.market_context.default_fx_ports import (
    DefaultFxSessionPort,
    DefaultLiquidityProfilePort,
    DefaultVolatilityProfilePort,
    SystemClockPort,
    WeekendCalendarPort,
)
from app.infrastructure.news.configured_feed import (
    ConfiguredHttpEconomicCalendar,
    ConfiguredHttpNewsFeed,
    NullEconomicCalendar,
    NullNewsFeed,
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


def get_news_intelligence(
    settings: Annotated[Settings, Depends(get_settings)],
) -> NewsIntelligenceService:
    news_url = (getattr(settings, "news_intelligence_feed_url", None) or "").strip()
    cal_url = (getattr(settings, "economic_calendar_feed_url", None) or "").strip()
    news_feed = (
        ConfiguredHttpNewsFeed(url=news_url) if news_url else NullNewsFeed()
    )
    calendar = (
        ConfiguredHttpEconomicCalendar(url=cal_url)
        if cal_url
        else NullEconomicCalendar()
    )
    return NewsIntelligenceService(news_feed=news_feed, calendar=calendar)


def get_portfolio_sync_for_intel(
    adapter: Annotated[MT5Adapter, Depends(get_mt5_adapter)],
) -> PortfolioSyncService:
    return PortfolioSyncService(adapter=adapter)


def get_market_intelligence(
    settings: Annotated[Settings, Depends(get_settings)],
    adapter: Annotated[MT5Adapter, Depends(get_mt5_adapter)],
    uow_factory: Annotated[Any, Depends(get_mt5_uow_factory)],
) -> MarketIntelligenceService:
    return MarketIntelligenceService(
        status=GetMT5StatusUseCase(uow_factory=uow_factory, adapter=adapter),
        symbols=ListMT5SymbolsUseCase(uow_factory=uow_factory, adapter=adapter),
        portfolio_sync=PortfolioSyncService(adapter=adapter),
        market_context=get_market_context_engine(),
        news=get_news_intelligence(settings),
        advisor=AiMarketAdvisor(),
    )


MarketIntelSvc = Annotated[MarketIntelligenceService, Depends(get_market_intelligence)]
NewsIntelSvc = Annotated[NewsIntelligenceService, Depends(get_news_intelligence)]
