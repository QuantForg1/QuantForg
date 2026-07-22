"""Scalping AI V2 API — continuous advisory loop; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.scalping_ai_v2 import ScalpingAiV2Service
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/scalping-ai-v2", tags=["scalping-ai-v2"])

_service = ScalpingAiV2Service()


class CycleRequest(BaseModel):
    side: str = "buy"
    bid: float | str | None = None
    ask: float | str | None = None
    spread: float | str | None = None
    atr: float | str | None = None
    price: float | str | None = None
    regime: str | None = None
    session: str | None = None
    trend: str | None = None
    volatility: str | None = None
    liquidity_state: str | None = None
    market_health: str | None = None
    confidence: float | str | None = None
    htf_bias: str | None = None
    ltf_confirmation: str | None = None
    trend_strength: float | str | None = None
    trend_consistency: float | str | None = None
    sweep_detected: bool | None = None
    equal_highs_lows: bool | None = None
    session_liquidity: str | None = None
    liquidity_side: str | None = None
    stop_hunt: bool | None = None
    bos: bool | None = None
    choch: bool | None = None
    mss: bool | None = None
    swing_bias: str | None = None
    structure_phase: str | None = None
    opportunities: list[dict[str, Any]] | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    decision_center: dict[str, Any] | None = None
    decision_approved: bool | None = None
    broker_connected: bool | None = None
    gateway_healthy: bool | None = None
    latency_ms: float | str | None = None
    market_open: bool | None = None
    margin_available: bool | None = None
    max_latency_ms: float | str | None = None
    equity: float | str | None = None
    daily_loss_pct: float | str | None = None
    open_exposure_pct: float | str | None = None
    trades_today: int | None = None
    consecutive_losses: int | None = None
    active_trade: dict[str, Any] | None = None
    closed_trade: dict[str, Any] | None = None
    health: dict[str, Any] | None = None
    run_state: str | None = None
    kill_switch: bool | None = None
    news_blackout: bool | None = None
    technique: str | None = None
    execution_identity: str | None = None


class PoliciesRequest(BaseModel):
    min_market_quality: float | str | None = None
    min_confidence: float | str | None = None
    max_spread: float | str | None = None
    min_quality_score: float | str | None = None
    min_execution_score: float | str | None = None
    max_risk_score: float | str | None = None
    base_risk_pct: float | str | None = None
    risk_floor_pct: float | str | None = None
    max_daily_loss_pct: float | str | None = None
    max_trades_per_day: int | None = Field(default=None, ge=1, le=500)
    max_open_exposure_pct: float | str | None = None
    break_even_enabled: bool | None = None
    trailing_enabled: bool | None = None
    partial_exit_enabled: bool | None = None
    max_retries: int | None = Field(default=None, ge=0, le=20)
    retry_backoff_ms: int | None = Field(default=None, ge=10, le=60_000)
    max_retry_backoff_ms: int | None = Field(default=None, ge=100, le=300_000)
    allowed_sessions: list[str] | None = None
    feature_flags: dict[str, bool] | None = None


@router.get("/status")
async def scalping_ai_v2_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/cycle")
async def scalping_ai_v2_cycle(
    body: CycleRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.cycle(body.model_dump())


@router.get("/events")
async def scalping_ai_v2_events(
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
    cycle_id: str | None = None,
) -> dict[str, Any]:
    _ = user
    return _service.events(limit=limit, cycle_id=cycle_id)


@router.get("/history")
async def scalping_ai_v2_history(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.history(limit=limit)


@router.get("/policies")
async def scalping_ai_v2_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def scalping_ai_v2_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
