"""Institutional AI Decision Engine V1 API.

Dry-run by default. Never order_send. Never enables EXECUTION_ENABLED.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.application.services.institutional_ai_decision import (
    InstitutionalAiDecisionService,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/institutional-decision",
    tags=["institutional-ai-decision"],
)

_service = InstitutionalAiDecisionService()


class LayerHintsRequest(BaseModel):
    trend_aligned: bool | None = None
    trend_label: str | None = None
    structure_valid: bool | None = None
    structure_bias: str | None = None
    liquidity_ok: bool | None = None
    liquidity_note: str | None = None
    order_block_valid: bool | None = None
    order_block_note: str | None = None
    fvg_valid: bool | None = None
    fvg_note: str | None = None
    spread: float | str | None = None
    atr: float | str | None = None
    price: float | str | None = None
    risk_engine_passed: bool | None = None
    risk_reason: str | None = None
    safety_engine_passed: bool | None = None
    safety_reason: str | None = None


class DecisionEvaluateRequest(BaseModel):
    side: str = "buy"
    strategy_id: str = "default"
    technique: str | None = None
    dry_run: bool = True
    equity: float | str = 10000
    stop_distance: float | str = 5
    consecutive_losses: int = 0
    daily_drawdown_pct: float | str = 0
    closed_pnls: list[float | str] = Field(default_factory=list)
    open_side: str | None = None
    open_unrealized_pnl: float | str | None = None
    spread: float | str | None = None
    atr: float | str | None = None
    price: float | str | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    layers: LayerHintsRequest = Field(default_factory=LayerHintsRequest)


@router.get("/status")
async def institutional_decision_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def institutional_decision_evaluate(
    body: DecisionEvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    """Run multi-layer decision pipeline. Dry-run — does not place orders."""
    _ = user
    return _service.evaluate(body.model_dump())
