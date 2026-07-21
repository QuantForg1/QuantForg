"""Alpha Engine V1 API — market quality scoring; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.alpha_engine import AlphaEngineService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/alpha-engine", tags=["alpha-engine"])

_service = AlphaEngineService()


class EvaluateRequest(BaseModel):
    side: str = "buy"
    technique: str | None = None
    regime: dict[str, Any] | None = None
    liquidity: dict[str, Any] | None = None
    structure: dict[str, Any] | None = None
    order_flow: dict[str, Any] | None = None
    opportunities: list[dict[str, Any]] | None = None
    execution: dict[str, Any] | None = None
    exit_context: dict[str, Any] | None = None
    trade_factors: dict[str, Any] | None = None
    closed_trades: list[dict[str, Any]] | None = None


class PoliciesRequest(BaseModel):
    min_regime_score: float | str | None = None
    min_liquidity_score: float | str | None = None
    min_structure_score: float | str | None = None
    min_order_flow_score: float | str | None = None
    min_confluence_score: float | str | None = None
    min_opportunity_score: float | str | None = None
    min_execution_score: float | str | None = None
    min_exit_score: float | str | None = None
    min_trade_score: float | str | None = None
    min_continuous_score: float | str | None = None
    min_composite_for_quality_ok: float | str | None = None
    max_spread_for_high_liquidity: float | str | None = None
    max_spread_acceptable: float | str | None = None
    high_vol_atr_pct: float | str | None = None
    low_vol_atr_pct: float | str | None = None
    max_ranked_opportunities: int | None = None
    max_history: int | None = Field(default=None, ge=10, le=500)


@router.get("/status")
async def alpha_engine_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def alpha_engine_evaluate(
    body: EvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.evaluate(body.model_dump())


@router.get("/history")
async def alpha_engine_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/replay")
async def alpha_engine_replay(
    user: CurrentUser,
    audit_id: str = Query(..., min_length=8, max_length=64),
) -> dict[str, Any]:
    _ = user
    return _service.replay(audit_id)


@router.get("/policies")
async def alpha_engine_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def alpha_engine_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
