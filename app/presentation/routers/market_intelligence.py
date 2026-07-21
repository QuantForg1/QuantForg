"""Market Intelligence Engine V1 API — evaluate only; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.application.services.market_intelligence import MarketIntelligenceService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/market-intelligence",
    tags=["market-intelligence"],
)

_service = MarketIntelligenceService()


class RegimeRequest(BaseModel):
    trend: str | None = None
    atr: float | str | None = None
    price: float | str | None = None
    news_driven: bool | None = None
    structure_label: str | None = None


class StrategySignalRequest(BaseModel):
    strategy_id: str
    enabled: bool = True
    side: str = "buy"
    confidence: float | str = 0
    notes: str = ""


class OpportunityRequest(BaseModel):
    signal_id: str
    strategy_id: str
    side: str = "buy"
    confidence: float | str = 0
    score: float | str | None = None
    notes: str = ""


class ExecutionQualityRequest(BaseModel):
    entry_quality: float | str | None = None
    exit_quality: float | str | None = None
    timing_quality: float | str | None = None
    sample_note: str | None = None


class PortfolioRiskRequest(BaseModel):
    equity: float | str | None = None
    allocated_pct: float | str | None = None
    daily_risk_used_pct: float | str | None = None


class AiHealthRequest(BaseModel):
    decision_quality: float | str | None = None
    execution_success: float | str | None = None
    risk_discipline: float | str | None = None
    system_reliability: float | str | None = None


class DayTradeRequest(BaseModel):
    trade_id: str
    side: str = "buy"
    pnl: float | str | None = None
    accepted: bool | None = None
    notes: str = ""


class ViolationRequest(BaseModel):
    code: str
    detail: str = ""


class MarketIntelligenceEvaluateRequest(BaseModel):
    regime: RegimeRequest = Field(default_factory=RegimeRequest)
    strategy_signals: list[StrategySignalRequest] = Field(default_factory=list)
    opportunities: list[OpportunityRequest] = Field(default_factory=list)
    execution_quality: ExecutionQualityRequest = Field(
        default_factory=ExecutionQualityRequest
    )
    portfolio_risk: PortfolioRiskRequest = Field(
        default_factory=PortfolioRiskRequest
    )
    ai_health: AiHealthRequest = Field(default_factory=AiHealthRequest)
    day_trades: list[DayTradeRequest] = Field(default_factory=list)
    violations: list[ViolationRequest] = Field(default_factory=list)
    technique: str | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None


@router.get("/status")
async def market_intelligence_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/evaluate")
async def market_intelligence_evaluate(
    body: MarketIntelligenceEvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    """Run Market Intelligence V1. Does not place orders."""
    _ = user
    return _service.evaluate(body.model_dump())
