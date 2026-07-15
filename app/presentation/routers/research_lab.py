"""Quant Research Lab API — strategy research center (analysis only).

Never order_send. Never flips EXECUTION_ENABLED. Never mutates broker / positions.
Decision Engine remains the promotion gatekeeper.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.research_lab import ResearchLabSvc

router = APIRouter(prefix="/research-lab", tags=["research-lab"])


class ValidateRequest(BaseModel):
    strategy_key: str = Field(..., max_length=64)
    symbol: str = Field(default="EURUSD", max_length=32)
    timeframe: str = Field(default="H1", max_length=16)
    count: int = Field(default=300, ge=50, le=2000)
    initial_balance: str = Field(default="10000")
    parameter_overrides: dict[str, Any] = Field(default_factory=dict)
    run_walkforward: bool = True
    run_monte_carlo: bool = True
    save_run: bool = True


class ParameterLabRequest(BaseModel):
    overrides: dict[str, Any] = Field(default_factory=dict)


class PromotionCriteriaRequest(BaseModel):
    min_profit_factor: float | None = None
    min_sharpe: float | None = None
    max_drawdown_pct: float | None = None
    min_trades: float | None = None
    min_stability: float | None = None
    require_walkforward: bool | None = None


class PromoteRequest(BaseModel):
    strategy_key: str = Field(..., max_length=64)
    run_id: str | None = None


@router.get("/dashboard")
async def research_dashboard(
    user: CurrentUser,
    lab: ResearchLabSvc,
    symbol: str = Query(default="EURUSD", max_length=32),
) -> dict[str, Any]:
    return await lab.dashboard(user_id=user.id, symbol=symbol)


@router.get("/library")
async def strategy_library(
    user: CurrentUser,
    lab: ResearchLabSvc,
) -> dict[str, Any]:
    _ = user
    return lab.strategy_library()


@router.post("/validate")
async def validate_strategy(
    body: ValidateRequest,
    user: CurrentUser,
    lab: ResearchLabSvc,
) -> dict[str, Any]:
    return await lab.validate_strategy(
        user_id=user.id,
        strategy_key=body.strategy_key,
        symbol=body.symbol,
        timeframe=body.timeframe,
        count=body.count,
        initial_balance=body.initial_balance,
        parameter_overrides=body.parameter_overrides or None,
        run_walkforward=body.run_walkforward,
        run_monte_carlo_flag=body.run_monte_carlo,
        save_run=body.save_run,
    )


@router.get("/compare")
async def compare_strategies(
    user: CurrentUser,
    lab: ResearchLabSvc,
) -> dict[str, Any]:
    return lab.compare(user_id=user.id)


@router.get("/regime")
async def regime_snapshot(
    user: CurrentUser,
    lab: ResearchLabSvc,
    symbol: str = Query(default="EURUSD", max_length=32),
) -> dict[str, Any]:
    return await lab.regime_snapshot(user_id=user.id, symbol=symbol)


@router.get("/parameters")
async def get_parameters(
    user: CurrentUser,
    lab: ResearchLabSvc,
) -> dict[str, Any]:
    return lab.get_parameters(user_id=user.id)


@router.post("/parameters")
async def parameter_lab(
    body: ParameterLabRequest,
    user: CurrentUser,
    lab: ResearchLabSvc,
) -> dict[str, Any]:
    return lab.parameter_lab(user_id=user.id, overrides=body.overrides)


@router.get("/paper")
async def paper_performance(
    user: CurrentUser,
    lab: ResearchLabSvc,
) -> dict[str, Any]:
    return lab.paper_performance(user_id=user.id)


@router.get("/promotion/criteria")
async def get_promotion_criteria(
    user: CurrentUser,
    lab: ResearchLabSvc,
) -> dict[str, Any]:
    _ = user
    return lab.promotion_criteria()


@router.post("/promotion/criteria")
async def set_promotion_criteria(
    body: PromotionCriteriaRequest,
    user: CurrentUser,
    lab: ResearchLabSvc,
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return lab.promotion_criteria(updates=updates or None)


@router.post("/promotion/evaluate")
async def evaluate_promotion(
    body: PromoteRequest,
    user: CurrentUser,
    lab: ResearchLabSvc,
) -> dict[str, Any]:
    return lab.promote(
        user_id=user.id,
        strategy_key=body.strategy_key,
        run_id=body.run_id,
    )


@router.get("/report")
async def research_report(
    user: CurrentUser,
    lab: ResearchLabSvc,
    strategy_key: str | None = Query(default=None, max_length=64),
) -> dict[str, Any]:
    return lab.report(user_id=user.id, strategy_key=strategy_key)
