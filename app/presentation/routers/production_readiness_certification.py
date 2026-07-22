"""PRC API — readiness certification only; never order_send / never auto-config."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.production_readiness_certification import (
    ProductionReadinessCertificationService,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/production-readiness-certification",
    tags=["production-readiness-certification"],
)

_service = ProductionReadinessCertificationService()


class EvaluateRequest(BaseModel):
    reliability: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    data: dict[str, Any] | None = None
    research: dict[str, Any] | None = None
    operations: dict[str, Any] | None = None
    prior_certification_status: str | None = None


class PoliciesRequest(BaseModel):
    pass_threshold: str | None = None
    watch_threshold: str | None = None
    max_history: int | None = Field(default=None, ge=10, le=10_000)
    feature_flags: dict[str, bool] | None = None


@router.get("/status")
async def prc_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def prc_evaluate(
    body: EvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.evaluate(body.model_dump())


@router.get("/history")
async def prc_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/policies")
async def prc_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def prc_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
