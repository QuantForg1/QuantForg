"""Intelligence Platform API — research only; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.intelligence_platform import IntelligencePlatformService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/intelligence-platform", tags=["intelligence-platform"])

_service = IntelligencePlatformService()


class KnowledgeBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)
    tags: list[str] = Field(default_factory=list)


class LiveFeedsBody(BaseModel):
    """Optional client-supplied recorded feeds (never fabricated server-side)."""

    execution_journal: list[dict[str, Any]] | None = None
    execution_audits: list[dict[str, Any]] | None = None
    execution_analytics: dict[str, Any] | None = None
    candles: list[dict[str, Any]] | None = None
    weekly_report: dict[str, Any] | None = None
    monthly_report: dict[str, Any] | None = None
    library: list[dict[str, Any]] | None = None
    closed_trades: list[dict[str, Any]] | None = None
    decision_replay: dict[str, Any] | None = None


class ReplayLoadBody(BaseModel):
    strategy_key: str = "research"
    bars: list[dict[str, Any]] = Field(default_factory=list)


class ReplayControlBody(BaseModel):
    action: str = Field(default="snapshot", max_length=32)


@router.get("/status")
async def intelligence_platform_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.get("/dashboard")
async def intelligence_platform_dashboard(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.dashboard()


@router.post("/dashboard")
async def intelligence_platform_dashboard_feeds(
    body: LiveFeedsBody, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.dashboard(
        execution_journal=body.execution_journal,
        execution_audits=body.execution_audits,
        execution_analytics=body.execution_analytics,
        candles=body.candles,
        weekly_report=body.weekly_report,
        monthly_report=body.monthly_report,
        library=body.library,
        closed_trades=body.closed_trades,
        decision_replay=body.decision_replay,
    )


@router.get("/knowledge")
async def intelligence_platform_knowledge(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.knowledge(limit=limit)


@router.post("/knowledge")
async def intelligence_platform_add_knowledge(
    body: KnowledgeBody, user: CurrentUser
) -> dict[str, Any]:
    author = str(
        getattr(user, "email", None) or getattr(user, "id", "") or "researcher"
    )
    return _service.add_knowledge(
        title=body.title, body=body.body, author=author, tags=body.tags
    )


@router.get("/knowledge/search")
async def intelligence_platform_search_knowledge(
    user: CurrentUser,
    q: str = Query(default="", max_length=200),
) -> dict[str, Any]:
    _ = user
    return _service.search_knowledge(q)


@router.post("/replay/load")
async def intelligence_platform_replay_load(
    body: ReplayLoadBody, user: CurrentUser
) -> dict[str, Any]:
    """Lab-isolated bar load — never touches production or broker."""
    _ = user
    return _service.replay_load(body.model_dump())


@router.post("/replay/control")
async def intelligence_platform_replay_control(
    body: ReplayControlBody, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.replay_control(body.action)


@router.get("/decision-replay")
async def intelligence_platform_decision_replay(
    user: CurrentUser,
    audit_id: str = Query(..., min_length=8, max_length=64),
) -> dict[str, Any]:
    _ = user
    return _service.decision_replay(audit_id)
