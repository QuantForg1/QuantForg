"""Multi-Agent AI API — collaborate before approval; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.multi_agent_ai import MultiAgentAIService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/multi-agent-ai", tags=["multi-agent-ai"])

_service = MultiAgentAIService()


class CollaborateRequest(BaseModel):
    side: str = "buy"
    spread: float | str | None = None
    confidence: float | str | None = None
    regime: str | None = None
    strategy_id: str | None = None
    strategy_signal: str | None = None
    portfolio_exposure: float | str | None = None
    open_positions: int | None = None
    execution_mode: str | None = None
    news_blackout: bool | None = None
    kill_switch: bool | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    market_snapshot: dict[str, Any] | None = None
    strategy_snapshot: dict[str, Any] | None = None
    portfolio_snapshot: dict[str, Any] | None = None
    execution_snapshot: dict[str, Any] | None = None


class PoliciesRequest(BaseModel):
    min_vote_confidence: float | str | None = None
    quorum_agents: int | None = Field(default=None, ge=1, le=6)
    max_events: int | None = Field(default=None, ge=100, le=10000)
    max_sessions: int | None = Field(default=None, ge=10, le=1000)
    max_memory: int | None = Field(default=None, ge=50, le=5000)
    feature_flags: dict[str, bool] | None = None


class MemoryStoreRequest(BaseModel):
    kind: str = "observation"
    agent: str = "operator"
    content: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None


@router.get("/status")
async def multi_agent_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/collaborate")
async def multi_agent_collaborate(
    body: CollaborateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.collaborate(body.model_dump())


@router.get("/events")
async def multi_agent_events(
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
    session_id: str | None = None,
) -> dict[str, Any]:
    _ = user
    return _service.events(limit=limit, session_id=session_id)


@router.get("/memory")
async def multi_agent_memory(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    kind: str | None = None,
) -> dict[str, Any]:
    _ = user
    return _service.memory(limit=limit, kind=kind)


@router.post("/memory")
async def multi_agent_store_memory(
    body: MemoryStoreRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.store_memory(body.model_dump())


@router.get("/governance")
async def multi_agent_governance(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.governance()


@router.get("/policies")
async def multi_agent_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def multi_agent_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
