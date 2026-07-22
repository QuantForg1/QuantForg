"""Live Learning Program API — evidence only; never order_send / never auto-tune."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.live_learning_program import (
    LiveLearningProgramService,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/live-learning-program",
    tags=["live-learning-program"],
)

_service = LiveLearningProgramService()


class EvaluateRequest(BaseModel):
    completed_trades: list[dict[str, Any]] | None = None
    replay_results: dict[str, Any] | None = None
    paper_results: dict[str, Any] | None = None
    live_results: dict[str, Any] | None = None
    operator_feedback: list[dict[str, Any]] | None = None
    edge_score_series: list[dict[str, Any]] | None = None
    journal_entries: list[dict[str, Any]] | None = None
    confidence_pairs: list[dict[str, Any]] | None = None
    period: str | None = None


class PoliciesRequest(BaseModel):
    min_observations_for_edge: int | None = Field(
        default=None, ge=1, le=10_000
    )
    min_observations_for_calibration: int | None = Field(
        default=None, ge=1, le=10_000
    )
    min_evidence_for_live_change_rec: int | None = Field(
        default=None, ge=1, le=50_000
    )
    max_observations: int | None = Field(default=None, ge=10, le=100_000)
    max_feedback: int | None = Field(default=None, ge=10, le=50_000)
    max_journal: int | None = Field(default=None, ge=10, le=50_000)
    max_history: int | None = Field(default=None, ge=10, le=10_000)
    feature_flags: dict[str, bool] | None = None


@router.get("/status")
async def llp_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def llp_evaluate(
    body: EvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.evaluate(body.model_dump())


@router.get("/history")
async def llp_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/policies")
async def llp_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def llp_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
