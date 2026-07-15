"""Quant AI Decision Engine API — wait-biased institutional decisions.

Never order_send. Never flips EXECUTION_ENABLED. Paper mode by default.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.decision_engine import DecisionEngineSvc

router = APIRouter(prefix="/decision-engine", tags=["decision-engine"])


class EvaluateRequest(BaseModel):
    symbol: str = Field(default="EURUSD", max_length=32)
    mode: str = Field(default="paper", description="paper | live (live never auto-sends)")
    record_paper: bool = True
    force_refresh: bool = False


class PaperOutcomeRequest(BaseModel):
    signal_id: str
    simulated_pnl: float


@router.get("/dashboard")
async def decision_dashboard(
    user: CurrentUser,
    engine: DecisionEngineSvc,
    symbol: str = Query(default="EURUSD", max_length=32),
) -> dict[str, Any]:
    return await engine.dashboard(user_id=user.id, symbol=symbol)


@router.post("/evaluate")
async def evaluate_decision(
    body: EvaluateRequest,
    user: CurrentUser,
    engine: DecisionEngineSvc,
) -> dict[str, Any]:
    return await engine.evaluate(
        user_id=user.id,
        symbol=body.symbol,
        mode=body.mode,
        record_paper=body.record_paper,
        force_refresh=body.force_refresh,
    )


@router.get("/evaluate")
async def evaluate_decision_get(
    user: CurrentUser,
    engine: DecisionEngineSvc,
    symbol: str = Query(default="EURUSD", max_length=32),
    mode: str = Query(default="paper"),
) -> dict[str, Any]:
    return await engine.evaluate(user_id=user.id, symbol=symbol, mode=mode)


@router.get("/paper/performance")
async def paper_performance(
    user: CurrentUser,
    engine: DecisionEngineSvc,
) -> dict[str, Any]:
    return engine.paper_performance(user.id)


@router.get("/reports")
async def decision_reports(
    user: CurrentUser,
    engine: DecisionEngineSvc,
) -> dict[str, Any]:
    return engine.reports(user.id)


@router.post("/paper/outcome")
async def paper_outcome(
    body: PaperOutcomeRequest,
    user: CurrentUser,
    engine: DecisionEngineSvc,
) -> dict[str, Any]:
    return engine.record_paper_outcome(
        user_id=user.id,
        signal_id=body.signal_id,
        simulated_pnl=body.simulated_pnl,
    )
