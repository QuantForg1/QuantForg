"""Research & Validation Platform API — never order_send / never live path."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.research_validation_platform import (
    ResearchValidationService,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/research-validation", tags=["research-validation"]
)

_service = ResearchValidationService()


class RegisterRequest(BaseModel):
    strategy_key: str | None = None
    name: str | None = None
    status: str | None = None
    notes: str | None = None


class ReplayLoadRequest(BaseModel):
    strategy_key: str = "unknown"
    version: str | None = None
    bars: list[dict[str, Any]] = Field(default_factory=list)


class WalkForwardRequest(BaseModel):
    strategy_key: str = "unknown"
    version: str | None = None
    folds: list[dict[str, Any]] | None = None


class PaperRequest(BaseModel):
    strategy_key: str = "unknown"
    version: str | None = None
    trade_count: int | None = None
    profit_factor: float | str | None = None
    max_drawdown_pct: float | str | None = None
    win_rate: float | str | None = None


class CompareRequest(BaseModel):
    runs: list[dict[str, Any]] = Field(default_factory=list)


class CertifyRequest(BaseModel):
    strategy_key: str = "unknown"
    version: str | None = None
    stage_results: dict[str, Any] | None = None


class VersionRequest(BaseModel):
    strategy_key: str = "unknown"
    version: str | None = None
    parameters: dict[str, Any] | None = None
    notes: str | None = None
    parent_version: str | None = None


class RollbackRequest(BaseModel):
    strategy_key: str = "unknown"
    target_version: str
    reason: str | None = None


class ObservatoryRequest(BaseModel):
    strategy_key: str = "unknown"
    version: str | None = None
    metrics: dict[str, Any] | None = None


class ReleaseRequest(BaseModel):
    strategy_key: str = "unknown"
    version: str | None = None
    certified: bool = False
    operator_approved: bool = False


class PoliciesRequest(BaseModel):
    min_profit_factor: float | str | None = None
    min_sharpe: float | str | None = None
    max_drawdown_pct: float | str | None = None
    min_trades: int | None = Field(default=None, ge=1, le=10000)
    min_walkforward_score: float | str | None = None
    min_paper_score: float | str | None = None
    min_certification_score: float | str | None = None
    require_operator_release_approval: bool | None = None
    max_replay_bars: int | None = Field(default=None, ge=10, le=50000)
    max_versions: int | None = Field(default=None, ge=10, le=5000)
    max_audit: int | None = Field(default=None, ge=10, le=10000)
    max_comparisons: int | None = Field(default=None, ge=2, le=100)
    feature_flags: dict[str, bool] | None = None


@router.get("/status")
async def rvp_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.get("/registry")
async def rvp_registry(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.registry()


@router.post("/registry")
async def rvp_register(
    body: RegisterRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.register(body.model_dump())


@router.post("/replay/load")
async def rvp_replay_load(
    body: ReplayLoadRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.replay_load(body.model_dump())


@router.post("/replay/step")
async def rvp_replay_step(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.replay_step()


@router.post("/walk-forward")
async def rvp_walk_forward(
    body: WalkForwardRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.walk_forward(body.model_dump())


@router.post("/paper")
async def rvp_paper(body: PaperRequest, user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.paper(body.model_dump())


@router.post("/compare")
async def rvp_compare(
    body: CompareRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.compare(body.model_dump())


@router.post("/certify")
async def rvp_certify(
    body: CertifyRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.certify(body.model_dump())


@router.post("/versions")
async def rvp_record_version(
    body: VersionRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.record_version(body.model_dump())


@router.get("/versions")
async def rvp_list_versions(
    user: CurrentUser,
    strategy_key: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.versions(strategy_key=strategy_key, limit=limit)


@router.post("/rollback")
async def rvp_rollback(
    body: RollbackRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.rollback(body.model_dump())


@router.get("/rollback/audit")
async def rvp_rollback_audit(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.rollback_audit(limit=limit)


@router.post("/observatory")
async def rvp_observatory(
    body: ObservatoryRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.observatory(body.model_dump())


@router.post("/release")
async def rvp_release(
    body: ReleaseRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.release(body.model_dump())


@router.get("/policies")
async def rvp_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def rvp_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
