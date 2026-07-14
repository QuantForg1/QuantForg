"""Quant AI API — institutional trading intelligence (analysis only).

Never order_send. Never flips EXECUTION_ENABLED. Never mutates orders.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.quant_ai import QuantAISvc

router = APIRouter(prefix="/quant-ai", tags=["quant-ai"])


class TradeReviewRequest(BaseModel):
    trade: dict[str, Any] = Field(default_factory=dict)


@router.get("/dashboard")
async def quant_ai_dashboard(
    user: CurrentUser,
    quant: QuantAISvc,
    symbol: str | None = Query(default=None, max_length=32),
    force_refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Full Quant AI snapshot — advisory intelligence only."""
    return await quant.dashboard(
        user_id=user.id,
        symbol=symbol,
        force_refresh=force_refresh,
    )


@router.get("/symbol/{symbol}")
async def quant_ai_symbol(
    symbol: str,
    user: CurrentUser,
    quant: QuantAISvc,
) -> dict[str, Any]:
    """Explainable structure brief for one symbol (why + confidence)."""
    return await quant.symbol_brief(user_id=user.id, symbol=symbol)


@router.get("/portfolio")
async def quant_ai_portfolio(
    user: CurrentUser,
    quant: QuantAISvc,
) -> dict[str, Any]:
    """Portfolio AI — win rate, RR, sessions, mistakes from real history."""
    return await quant.portfolio_brief(user_id=user.id)


@router.get("/risk")
async def quant_ai_risk(
    user: CurrentUser,
    quant: QuantAISvc,
) -> dict[str, Any]:
    """Risk AI — leverage / margin / correlation / drawdown flags."""
    return await quant.risk_brief(user_id=user.id)


@router.get("/execution")
async def quant_ai_execution(
    user: CurrentUser,
    quant: QuantAISvc,
) -> dict[str, Any]:
    """Execution AI — slippage / latency / fill quality from real attempts."""
    return await quant.execution_brief(user_id=user.id)


@router.post("/trade-review")
async def quant_ai_trade_review(
    body: TradeReviewRequest,
    user: CurrentUser,
    quant: QuantAISvc,
) -> dict[str, Any]:
    """Per-trade AI review labels — never modifies the trade."""
    return await quant.trade_review(user_id=user.id, trade=body.trade)
