"""Strategy Research Lab API — validation & promotion only.

Never order_send. Completely separated from live execution.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.strategy_research_lab import StrategyResearchLabService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/strategy-lab", tags=["strategy-research-lab"])

_service = StrategyResearchLabService()


class CompareRequest(BaseModel):
    runs: list[dict[str, Any]] = Field(default_factory=list)


class MetricsRequest(BaseModel):
    strategy_key: str
    profit_factor: float | str | None = None
    sharpe: float | str | None = None
    max_drawdown_pct: float | str | None = None
    trade_count: int | None = None
    win_rate: float | str | None = None
    stability: float | str | None = None
    notes: list[str] = Field(default_factory=list)
    validation_passed: bool | None = None


class ReplayLoadRequest(BaseModel):
    strategy_key: str
    bars: list[dict[str, Any]] = Field(default_factory=list)


class ReplayControlRequest(BaseModel):
    action: str = Field(description="start | pause | resume | step | status")


class ExperimentCreateRequest(BaseModel):
    strategy_key: str
    variants: list[dict[str, Any]] = Field(default_factory=list)


class ExperimentResultsRequest(BaseModel):
    batch_id: str
    results: list[dict[str, Any]] = Field(default_factory=list)


class VersionRequest(BaseModel):
    strategy_key: str
    version: str = "0.0.1"
    parameters: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    created_by: str = "operator"


class ApprovalRequest(BaseModel):
    case_id: str
    decision: str = Field(description="approve | reject")
    operator: str = "operator"
    reason: str = ""


@router.get("/status")
async def strategy_lab_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.get("/registry")
async def strategy_lab_registry(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.registry()


@router.post("/compare")
async def strategy_lab_compare(
    body: CompareRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.compare(body.runs)


@router.post("/scorecard")
async def strategy_lab_scorecard(
    body: MetricsRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.scorecard(body.model_dump())


@router.post("/validate")
async def strategy_lab_validate(
    body: MetricsRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.validate(body.model_dump())


@router.post("/replay/load")
async def strategy_lab_replay_load(
    body: ReplayLoadRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.replay_load(body.model_dump())


@router.post("/replay/control")
async def strategy_lab_replay_control(
    body: ReplayControlRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.replay_control(body.action)


@router.post("/experiments")
async def strategy_lab_experiments_create(
    body: ExperimentCreateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.experiment_create(body.model_dump())


@router.post("/experiments/results")
async def strategy_lab_experiments_results(
    body: ExperimentResultsRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    out = _service.experiment_results(body.model_dump())
    return out or {"error": "batch_not_found"}


@router.get("/experiments")
async def strategy_lab_experiments_list(
    user: CurrentUser,
    strategy_key: str | None = Query(default=None),
) -> dict[str, Any]:
    _ = user
    return {"batches": _service.experiment_list(strategy_key)}


@router.post("/versions")
async def strategy_lab_version_record(
    body: VersionRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.version_record(body.model_dump())


@router.get("/versions")
async def strategy_lab_versions(
    user: CurrentUser,
    strategy_key: str = Query(..., max_length=64),
) -> dict[str, Any]:
    _ = user
    return {"versions": _service.version_list(strategy_key)}


@router.post("/promotion/open")
async def strategy_lab_promotion_open(
    body: MetricsRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.promotion_open(body.model_dump())


@router.post("/promotion/approve")
async def strategy_lab_promotion_approve(
    body: ApprovalRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    out = _service.promotion_approve(body.model_dump())
    return out or {"error": "case_not_found"}


@router.get("/promotion/dashboard")
async def strategy_lab_promotion_dashboard(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.promotion_dashboard()
