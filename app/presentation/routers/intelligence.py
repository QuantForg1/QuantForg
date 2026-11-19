"""Market Intelligence API — real MT5 sync, context, configured news, advisor."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.public_market_feed import PublicMarketFeedService
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.intelligence import (
    MarketIntelSvc,
    NewsIntelSvc,
    ProviderRegistrySvc,
)
from app.presentation.dependencies.mt5 import get_mt5_market_data
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
    """Return events from the configured calendar feed, or an empty list."""
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
    """Classify real news and calendar payloads without fabricating events."""
    portfolio_symbols: tuple[str, ...] = ()
    try:
        dash = await intel.dashboard(user_id=user.id)
        portfolio_symbols = tuple(
            str(p.get("symbol"))
            for p in (dash.get("positions") or [])
            if isinstance(p, dict) and p.get("symbol")
        )
    except Exception:
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
    return IntelligenceStatusResponse(**cast("dict[str, Any]", registry.status()))


# --- QuantForg AI Assistant (grounded chat + chart screenshots) -------------


class _AssistantTurn(BaseModel):
    role: str = Field(default="user", max_length=16)
    content: str = Field(default="", max_length=8000)


class AssistantChatBody(BaseModel):
    message: str = Field(default="", max_length=4000)
    history: list[_AssistantTurn] = Field(default_factory=list, max_length=40)
    images: list[str] = Field(default_factory=list, max_length=3)


def _assistant_feed(
    market_data: Annotated[MT5MarketDataService, Depends(get_mt5_market_data)],
) -> PublicMarketFeedService:
    return PublicMarketFeedService(market_data=market_data)


def _risk_settings_for(user_id: Any) -> dict[str, Any] | None:
    try:
        from app.application.services.user_risk_preferences_service import (
            get_user_risk_preferences,
        )

        prefs = get_user_risk_preferences(user_id)
    except Exception:
        return None
    if not isinstance(prefs, dict):
        return None
    keep = (
        "planned_risk_pct",
        "daily_loss_pct",
        "aggregate_open_risk_pct",
        "max_lot",
        "max_concurrent_positions",
    )
    nested = prefs.get("preferences")
    src: dict[str, Any] = nested if isinstance(nested, dict) else prefs
    out = {k: str(src.get(k)) for k in keep if src.get(k) is not None}
    return out or None


async def _ensure_assistant_access(user: Any) -> None:
    from app.application.services import market_assistant as ma
    from app.application.services.admin_management import feature_allowed

    if str(getattr(user, "role", "")).lower() in {"owner", "admin"}:
        return
    if not await asyncio.to_thread(feature_allowed, user.id, "ai_assistant"):
        raise ma.AssistantError(
            "access_removed",
            "AI Assistant access was removed for your account. Contact support.",
            403,
        )


async def _assistant_prepare(
    body: AssistantChatBody, user: Any, news: Any, feed: Any
) -> tuple[Any, list[Any], str, list[str], dict[str, Any]]:
    from app.application.services import market_assistant as ma
    from core.config.settings import get_settings

    message = body.message.strip()
    if not message and not body.images:
        raise ma.AssistantError("empty_message", "Type a question or attach a chart.")
    await _ensure_assistant_access(user)
    ma.check_rate_limit(str(user.id))
    images = [ma.validate_image(u) for u in body.images[: ma.MAX_IMAGES]]
    history = ma.clean_history([ma.ChatTurn(t.role, t.content) for t in body.history])
    snapshot = await ma.cached_market_snapshot(feed=feed, news=news)
    risk = await asyncio.to_thread(_risk_settings_for, user.id)
    if risk:
        snapshot["user_risk_settings"] = risk
    return ma.assistant_client(get_settings()), history, message, images, snapshot


def _assistant_http_error(exc: Any) -> HTTPException:
    return HTTPException(
        status_code=exc.status, detail={"code": exc.code, "message": exc.message}
    )


@router.post("/assistant/chat")
async def assistant_chat(
    body: AssistantChatBody,
    user: CurrentUser,
    news: NewsIntelSvc,
    feed: Annotated[PublicMarketFeedService, Depends(_assistant_feed)],
) -> dict[str, Any]:
    """Grounded AI answer (non-streaming fallback). Advisory only."""
    from app.application.services import market_assistant as ma

    try:
        client, history, message, images, snapshot = await _assistant_prepare(
            body, user, news, feed
        )
        return await ma.chat(
            client=client,
            history=history,
            message=message,
            images=images,
            snapshot=snapshot,
        )
    except ma.AssistantError as exc:
        raise _assistant_http_error(exc) from exc


@router.post("/assistant/stream")
async def assistant_stream(
    body: AssistantChatBody,
    user: CurrentUser,
    news: NewsIntelSvc,
    feed: Annotated[PublicMarketFeedService, Depends(_assistant_feed)],
) -> StreamingResponse:
    """Same as /assistant/chat, streamed as server-sent events with live
    analysis stages. Validation happens before the stream opens."""
    from app.application.services import market_assistant as ma
    from core.config.settings import get_settings

    message = body.message.strip()
    try:
        if not message and not body.images:
            raise ma.AssistantError(
                "empty_message", "Type a question or attach a chart."
            )
        await _ensure_assistant_access(user)
        ma.check_rate_limit(str(user.id))
        images = [ma.validate_image(u) for u in body.images[: ma.MAX_IMAGES]]
    except ma.AssistantError as exc:
        raise _assistant_http_error(exc) from exc
    history = ma.clean_history([ma.ChatTurn(t.role, t.content) for t in body.history])

    async def snapshot_provider() -> dict[str, Any]:
        snap = await ma.cached_market_snapshot(feed=feed, news=news)
        risk = await asyncio.to_thread(_risk_settings_for, user.id)
        if risk:
            snap["user_risk_settings"] = risk
        return snap

    return StreamingResponse(
        ma.stream_chat(
            client=ma.assistant_client(get_settings()),
            history=history,
            message=message,
            images=images,
            snapshot_provider=snapshot_provider,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/desk")
async def intelligence_desk(
    user: CurrentUser,
    news: NewsIntelSvc,
    feed: Annotated[PublicMarketFeedService, Depends(_assistant_feed)],
) -> dict[str, Any]:
    """Computed gold market desk: trend per timeframe, levels, volatility,
    session, and a trade-conditions checklist. Same data the AI reads."""
    from app.application.services import market_assistant as ma

    _ = user
    snap = await ma.cached_market_snapshot(feed=feed, news=news)
    return {
        "snapshot": snap,
        "conditions": ma.trade_conditions(snap),
    }


_PUBLIC_STRATEGY_FIELDS = (
    "key",
    "name",
    "family",
    "description",
    "best_regimes",
    "engine_plugin",
)


@router.get("/strategies")
async def intelligence_strategies(user: CurrentUser) -> dict[str, Any]:
    """Read-only strategy catalogue for the customer Strategy Lab desk.

    The Strategy Lab router itself is operator-only (it has write actions);
    customers get the public description fields only, nothing internal.
    """
    _ = user
    from app.application.services.strategy_research_lab import (
        StrategyResearchLabService,
    )

    registry = await asyncio.to_thread(StrategyResearchLabService().registry)
    rows = registry.get("strategies") if isinstance(registry, dict) else None
    strategies = [
        {k: r.get(k) for k in _PUBLIC_STRATEGY_FIELDS}
        for r in (rows if isinstance(rows, list) else [])
        if isinstance(r, dict)
    ]
    return {"strategies": strategies, "count": len(strategies)}
