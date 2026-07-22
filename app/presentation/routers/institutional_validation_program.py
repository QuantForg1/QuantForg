"""Institutional Validation Program API — read-only evidence; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.institutional_validation_program import (
    InstitutionalValidationProgramService,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/institutional-validation-program",
    tags=["institutional-validation-program"],
)

_service = InstitutionalValidationProgramService()


class EvaluateRequest(BaseModel):
    completed_trades: list[dict[str, Any]] | None = None
    configurations: list[dict[str, Any]] | None = None
    risk_facts: dict[str, Any] | None = None
    replay_results: dict[str, Any] | None = None
    paper_results: dict[str, Any] | None = None
    strategy_id: str | None = None
    configuration_id: str | None = None
    history_event: dict[str, Any] | None = None


class PoliciesRequest(BaseModel):
    min_trades_for_evidence: int | None = Field(default=None, ge=1, le=10_000)
    min_trades_for_regime: int | None = Field(default=None, ge=1, le=1000)
    min_trades_for_comparison: int | None = Field(default=None, ge=1, le=1000)
    rolling_windows: list[int] | None = None
    confidence_z: str | None = None
    max_history: int | None = Field(default=None, ge=10, le=10_000)
    feature_flags: dict[str, bool] | None = None


@router.get("/status")
async def ivp_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def ivp_evaluate(
    body: EvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.evaluate(body.model_dump())


@router.get("/history")
async def ivp_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/policies")
async def ivp_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def ivp_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
