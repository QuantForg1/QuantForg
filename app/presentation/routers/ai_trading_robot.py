"""AI Trading Robot V1 API — evaluate / status / self-analysis.

Never order_send. Never enables EXECUTION_ENABLED.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.application.services.ai_trading_robot import AiTradingRobotService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/ai-robot", tags=["ai-trading-robot"])

_service = AiTradingRobotService()


class RobotEvaluateRequest(BaseModel):
    side: str = "buy"
    signal_present: bool = True
    strategy_id: str = "default"
    strategy_valid: bool = True
    technique: str | None = None
    equity: float | str = 10000
    stop_distance: float | str = 5
    spread: float | str | None = None
    atr: float | str | None = None
    price: float | str | None = None
    daily_drawdown_pct: float | str = 0
    consecutive_losses: int = 0
    cooldown_active: bool = False
    confluence: float | str | None = None
    trade_quality: float | str | None = None
    structure_bias_aligned: bool | None = None
    closed_pnls: list[float | str] = Field(default_factory=list)
    r_multiples: list[float | str] = Field(default_factory=list)
    journal_trades: list[dict[str, Any]] = Field(default_factory=list)
    open_side: str | None = None
    open_unrealized_pnl: float | str | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None


class SelfAnalysisRequest(BaseModel):
    strategy_id: str = "default"
    closed_pnls: list[float | str] = Field(default_factory=list)
    journal_trades: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/status")
async def ai_robot_status(user: CurrentUser) -> dict[str, Any]:
    """Robot V1 capability + policy surface (auth required)."""
    _ = user
    return _service.status()


@router.post("/evaluate")
async def ai_robot_evaluate(
    body: RobotEvaluateRequest, user: CurrentUser
) -> dict[str, Any]:
    """Run full Robot V1 evaluation pipeline. Does not place orders."""
    _ = user
    return _service.evaluate(body.model_dump())


@router.post("/self-analysis")
async def ai_robot_self_analysis(
    body: SelfAnalysisRequest, user: CurrentUser
) -> dict[str, Any]:
    """Discipline / capital-preservation self-analysis report."""
    _ = user
    return _service.self_analysis(body.model_dump())
