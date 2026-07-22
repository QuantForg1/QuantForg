"""IEE API — edge analytics; never order_send / never disables trading."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.institutional_edge_engine import (
    InstitutionalEdgeEngineService,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/institutional-edge-engine",
    tags=["institutional-edge-engine"],
)

_service = InstitutionalEdgeEngineService()


class EvaluateRequest(BaseModel):
    completed_trades: list[dict[str, Any]] | None = None
    discipline_facts: dict[str, Any] | None = None
    prior_edge_score: float | str | None = None
    research_month: str | None = None


class PoliciesRequest(BaseModel):
    min_trades_for_edge: int | None = Field(default=None, ge=1, le=10_000)
    min_trades_for_regime: int | None = Field(default=None, ge=1, le=1000)
    min_trades_for_entry_exit: int | None = Field(default=None, ge=1, le=1000)
    rolling_windows: list[int] | None = None
    edge_warning_threshold: float | str | None = None
    edge_critical_threshold: float | str | None = None
    stability_variance_warn: float | str | None = None
    feature_flags: dict[str, bool] | None = None


@router.get("/status")
async def iee_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def iee_evaluate(
    body: EvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.evaluate(body.model_dump())


@router.get("/history")
async def iee_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/policies")
async def iee_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def iee_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
