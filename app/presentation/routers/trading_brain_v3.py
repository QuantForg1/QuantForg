"""Trading Brain V3 API — capital preservation orchestration; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.trading_brain_v3 import TradingBrainV3Service
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/trading-brain-v3", tags=["trading-brain-v3"])

_service = TradingBrainV3Service()


class EvaluateRequest(BaseModel):
    side: str = "buy"
    spread: float | str | None = None
    atr: float | str | None = None
    regime: str | None = None
    session: str | None = None
    news_blackout: bool | None = None
    kill_switch: bool | None = None
    confidence: float | str | None = None
    opportunity_candidates: list[dict[str, Any]] | None = None
    decision_center: dict[str, Any] | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    execution_mode: str | None = None
    open_positions: int | None = None
    unrealized_pnl: float | str | None = None
    active_trade: dict[str, Any] | None = None
    closed_trades: list[dict[str, Any]] | None = None
    quality_metrics: dict[str, Any] | None = None
    operator_notes: list[str] | None = None


class PoliciesRequest(BaseModel):
    min_environment_score: float | str | None = None
    min_opportunity_score: float | str | None = None
    min_rank_score: float | str | None = None
    min_challenge_pass_score: float | str | None = None
    min_execution_readiness: float | str | None = None
    min_discipline_score: float | str | None = None
    max_spread: float | str | None = None
    max_open_positions_soft: int | None = Field(default=None, ge=1, le=20)
    max_history: int | None = Field(default=None, ge=10, le=1000)
    feature_flags: dict[str, bool] | None = None


@router.get("/status")
async def trading_brain_v3_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def trading_brain_v3_evaluate(
    body: EvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.evaluate(body.model_dump())


@router.get("/history")
async def trading_brain_v3_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/policies")
async def trading_brain_v3_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def trading_brain_v3_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
