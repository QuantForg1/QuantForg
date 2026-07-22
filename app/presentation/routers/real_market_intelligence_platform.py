"""RMIP API — read-only market context; never order_send / never changes rules."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.real_market_intelligence_platform import (
    RealMarketIntelligencePlatformService,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/real-market-intelligence-platform",
    tags=["real-market-intelligence-platform"],
)

_service = RealMarketIntelligencePlatformService()


class EvaluateRequest(BaseModel):
    economic_events: list[dict[str, Any]] | None = None
    clock_utc: str | None = None
    session_hint: str | None = None
    volatility_observations: dict[str, Any] | None = None
    liquidity_observations: dict[str, Any] | None = None
    regime: str | None = None
    trend: str | None = None
    confidence: str | None = None
    archive_event: dict[str, Any] | None = None


class PoliciesRequest(BaseModel):
    max_archive: int | None = Field(default=None, ge=10, le=10_000)
    max_timeline: int | None = Field(default=None, ge=10, le=10_000)
    feature_flags: dict[str, bool] | None = None


@router.get("/status")
async def rmip_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def rmip_evaluate(
    body: EvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.evaluate(body.model_dump())


@router.get("/history")
async def rmip_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/policies")
async def rmip_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def rmip_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)


# Explicit Context API aliases (READ ONLY)
@router.get("/context/current")
async def rmip_current_context(user: CurrentUser) -> dict[str, Any]:
    _ = user
    status = _service.status()
    return {
        "status": "available",
        "read_only": True,
        "recent_timeline": status.get("recent_timeline"),
        "recent_archive": status.get("recent_archive"),
        "note": "POST /evaluate with live feeds for fresh context",
    }


@router.get("/context/historical")
async def rmip_historical_context(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)
