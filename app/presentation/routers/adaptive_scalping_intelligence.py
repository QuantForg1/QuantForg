"""ASI API — adaptive advisory intelligence; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.adaptive_scalping_intelligence import (
    AdaptiveScalpingIntelligenceService,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/adaptive-scalping-intelligence",
    tags=["adaptive-scalping-intelligence"],
)

_service = AdaptiveScalpingIntelligenceService()


class EvaluateRequest(BaseModel):
    side: str = "buy"
    session: str | None = None
    hour_utc: int | None = Field(default=None, ge=0, le=23)
    weekday: str | None = None
    regime: str | None = None
    volatility: str | None = None
    spread: float | str | None = None
    personality_hint: str | None = None
    pattern_id: str | None = None
    live_confidence: float | str | None = None
    live_opportunity: dict[str, Any] | None = None
    capital_facts: dict[str, Any] | None = None
    decision_context: dict[str, Any] | None = None
    historical_observations: list[dict[str, Any]] | None = None
    closed_trades: list[dict[str, Any]] | None = None
    opportunity_catalog: list[dict[str, Any]] | None = None


class PoliciesRequest(BaseModel):
    min_history_observations: int | None = Field(default=None, ge=1, le=10_000)
    min_session_samples: int | None = Field(default=None, ge=1, le=1000)
    min_pattern_samples: int | None = Field(default=None, ge=1, le=1000)
    min_calibration_samples: int | None = Field(default=None, ge=1, le=1000)
    heat_map_buckets: int | None = Field(default=None, ge=2, le=24)
    coach_lookback_days: int | None = Field(default=None, ge=1, le=90)
    feature_flags: dict[str, bool] | None = None


@router.get("/status")
async def asi_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def asi_evaluate(
    body: EvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.evaluate(body.model_dump())


@router.get("/history")
async def asi_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/policies")
async def asi_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def asi_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
