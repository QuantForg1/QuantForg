"""Market Intelligence API — real MT5 sync, context, configured news, advisor."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.intelligence import MarketIntelSvc, NewsIntelSvc
from app.presentation.schemas.intelligence import (
    AnalysisResponse,
    EconomicEventResponse,
    IntelligenceDashboardResponse,
    MarketContextResponse,
    NewsItemResponse,
)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/dashboard", response_model=IntelligenceDashboardResponse)
async def intelligence_dashboard(
    user: CurrentUser,
    intel: MarketIntelSvc,
    market_code: str = Query(default="FX", max_length=32),
    symbol: str | None = Query(default=None, max_length=32),
) -> IntelligenceDashboardResponse:
    """Aggregate live MT5 portfolio/market state + context + configured feeds."""
    data = await intel.dashboard(
        user_id=user.id,
        market_code=market_code,
        symbol=symbol,
    )
    return IntelligenceDashboardResponse(**data)


@router.get("/market-context", response_model=MarketContextResponse)
async def market_context(
    user: CurrentUser,
    intel: MarketIntelSvc,
    market_code: str = Query(default="FX", max_length=32),
    symbol: str | None = Query(default=None, max_length=32),
) -> MarketContextResponse:
    """Deterministic trading session / volatility / liquidity profile."""
    _ = user
    return MarketContextResponse(
        **intel.market_context_only(market_code=market_code, symbol=symbol)
    )


@router.get("/news", response_model=list[NewsItemResponse])
async def intelligence_news(
    user: CurrentUser,
    news: NewsIntelSvc,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[NewsItemResponse]:
    """Return news only from configured ``NEWS_INTELLIGENCE_FEED_URL`` (else empty)."""
    _ = user
    return [
        NewsItemResponse(
            id=i.id,
            title=i.title,
            summary=i.summary,
            source=i.source,
            url=i.url,
            published_at=i.published_at,
            symbols=list(i.symbols),
        )
        for i in news.news(limit=limit)
    ]


@router.get("/calendar", response_model=list[EconomicEventResponse])
async def intelligence_calendar(
    user: CurrentUser,
    news: NewsIntelSvc,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[EconomicEventResponse]:
    """Return events only from configured ``ECONOMIC_CALENDAR_FEED_URL`` (else empty)."""
    _ = user
    return [
        EconomicEventResponse(
            id=e.id,
            title=e.title,
            country=e.country,
            impact=e.impact,
            scheduled_at=e.scheduled_at,
            actual=e.actual,
            forecast=e.forecast,
            previous=e.previous,
            source=e.source,
        )
        for e in news.economic_events(limit=limit)
    ]


@router.get("/analysis", response_model=AnalysisResponse)
async def intelligence_analysis(
    user: CurrentUser,
    intel: MarketIntelSvc,
    market_code: str = Query(default="FX", max_length=32),
    symbol: str | None = Query(default=None, max_length=32),
) -> AnalysisResponse:
    """Advisor summary from real snapshots — never places trades."""
    data = await intel.dashboard(
        user_id=user.id,
        market_code=market_code,
        symbol=symbol,
    )
    return AnalysisResponse(**data["analysis"])
