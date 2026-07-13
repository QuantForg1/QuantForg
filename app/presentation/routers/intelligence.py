"""Market Intelligence API — real MT5 sync, context, configured news, advisor."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.intelligence import (
    MarketIntelSvc,
    NewsIntelSvc,
    ProviderRegistrySvc,
)
from app.presentation.schemas.intelligence import (
    AnalysisResponse,
    EconomicEventResponse,
    IntelligenceDashboardResponse,
    IntelligenceEventResponse,
    IntelligenceStatusResponse,
    MarketContextResponse,
    NewsItemResponse,
    ProviderHealthResponse,
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


@router.get("/events", response_model=list[IntelligenceEventResponse])
async def intelligence_events(
    user: CurrentUser,
    registry: ProviderRegistrySvc,
    intel: MarketIntelSvc,
    limit: int = Query(default=30, ge=1, le=100),
) -> list[IntelligenceEventResponse]:
    """Classify real news/calendar payloads into intelligence events (no fabrication)."""
    portfolio_symbols: tuple[str, ...] = ()
    try:
        dash = await intel.dashboard(user_id=user.id)
        portfolio_symbols = tuple(
            str(p.get("symbol"))
            for p in (dash.get("positions") or [])
            if isinstance(p, dict) and p.get("symbol")
        )
    except Exception:  # noqa: BLE001
        portfolio_symbols = ()
    events = registry.build_events(limit=limit, portfolio_symbols=portfolio_symbols)
    return [
        IntelligenceEventResponse(
            id=e.id,
            title=e.title,
            summary=e.summary,
            classification=e.classification,
            severity=e.severity,
            affected_currencies=list(e.affected_currencies),
            affected_assets=list(e.affected_assets),
            affected_sectors=list(e.affected_sectors),
            expected_volatility=e.expected_volatility,
            portfolio_impact=e.portfolio_impact,
            risk_score=e.risk_score,
            provider=e.provider,
            source_url=e.source_url,
            published_at=e.published_at,
            deterministic_summary=e.deterministic_summary,
        )
        for e in events
    ]


@router.get("/providers", response_model=list[ProviderHealthResponse])
async def intelligence_providers(
    user: CurrentUser,
    registry: ProviderRegistrySvc,
) -> list[ProviderHealthResponse]:
    """Provider inventory with configuration, health, and metrics."""
    _ = user
    return [
        ProviderHealthResponse(
            name=h.name,
            kind=h.kind.value,
            status=h.status.value,
            configured=h.configured,
            priority=h.priority,
            latency_ms=h.latency_ms,
            last_error=h.last_error,
            last_success_at=h.last_success_at,
            requests=h.requests,
            failures=h.failures,
            cache_hits=h.cache_hits,
            rate_limited=h.rate_limited,
        )
        for h in registry.list_providers()
    ]


@router.get("/status", response_model=IntelligenceStatusResponse)
async def intelligence_status(
    user: CurrentUser,
    registry: ProviderRegistrySvc,
) -> IntelligenceStatusResponse:
    """Aggregate provider layer status (failover / cache / rate-limit posture)."""
    _ = user
    return IntelligenceStatusResponse(**registry.status())
