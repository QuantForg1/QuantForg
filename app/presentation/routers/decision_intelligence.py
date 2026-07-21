"""Decision Intelligence Center API — reject/hold gate; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.decision_intelligence import DecisionIntelligenceService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/decision-intelligence",
    tags=["decision-intelligence"],
)

_service = DecisionIntelligenceService()


class ConfidenceFactorsRequest(BaseModel):
    signal_strength: float | str | None = None
    structure_align: float | str | None = None
    consensus: float | str | None = None
    regime_fit: float | str | None = None
    execution_quality: float | str | None = None


class QualityRequest(BaseModel):
    approve_precision: float | str | None = None
    reject_precision: float | str | None = None
    override_rate: float | str | None = None
    audit_completeness: float | str | None = None


class EvaluateRequest(BaseModel):
    side: str = "buy"
    strategy_id: str = "default"
    technique: str | None = None
    signal_present: bool | None = None
    strategy_consensus_ok: bool | None = None
    market_regime_ok: bool | None = None
    confidence_factors: ConfidenceFactorsRequest = Field(
        default_factory=ConfidenceFactorsRequest
    )
    spread: float | str | None = None
    daily_drawdown_pct: float | str = 0
    consecutive_losses: int = 0
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    quality: QualityRequest = Field(default_factory=QualityRequest)
    operator_action: str | None = None
    operator: str = "system"
    operator_reason: str = ""


class PoliciesRequest(BaseModel):
    min_confidence: float | str | None = None
    high_confidence: float | str | None = None
    require_signal: bool | None = None
    require_strategy_consensus: bool | None = None
    require_market_regime_ok: bool | None = None
    max_spread: float | str | None = None
    max_daily_drawdown_pct: float | str | None = None
    max_consecutive_losses: int | None = None
    min_decision_quality: float | str | None = None
    max_history: int | None = None


@router.get("/status")
async def decision_intelligence_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def decision_intelligence_evaluate(
    body: EvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.evaluate(body.model_dump())


@router.get("/history")
async def decision_intelligence_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/replay")
async def decision_intelligence_replay(
    user: CurrentUser,
    audit_id: str = Query(..., min_length=8, max_length=64),
) -> dict[str, Any]:
    _ = user
    return _service.replay(audit_id)


@router.get("/policies")
async def decision_intelligence_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def decision_intelligence_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
