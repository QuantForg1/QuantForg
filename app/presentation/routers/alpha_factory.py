"""Alpha Factory API — research isolation; never order_send / never auto-promote."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.alpha_factory import AlphaFactoryService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/alpha-factory", tags=["alpha-factory"])

_service = AlphaFactoryService()


class EvaluateRequest(BaseModel):
    action: str = "evaluate"
    experiment: dict[str, Any] | None = None
    experiments: list[dict[str, Any]] | None = None
    strategy: dict[str, Any] | None = None
    strategies: list[dict[str, Any]] | None = None
    replay: dict[str, Any] | None = None
    paper: dict[str, Any] | None = None
    benchmarks: list[dict[str, Any]] | None = None
    promotion: dict[str, Any] | None = None
    history_event: dict[str, Any] | None = None
    score_inputs: dict[str, Any] | None = None
    author: str | None = None


class PoliciesRequest(BaseModel):
    min_trades_for_score: int | None = Field(default=None, ge=1, le=10_000)
    min_trades_for_benchmark: int | None = Field(default=None, ge=1, le=1000)
    max_experiments: int | None = Field(default=None, ge=10, le=10_000)
    feature_flags: dict[str, bool] | None = None


@router.get("/status")
async def alpha_factory_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def alpha_factory_evaluate(
    body: EvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.evaluate(body.model_dump())


@router.get("/history")
async def alpha_factory_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/policies")
async def alpha_factory_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def alpha_factory_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
