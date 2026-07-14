"""Quant Studio API — AI-assisted research workspace (analysis only).

Never order_send. Never flips EXECUTION_ENABLED. Never mutates broker state.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.quant_studio import QuantStudioSvc

router = APIRouter(prefix="/quant-studio", tags=["quant-studio"])


class GraphRequest(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class CompileRequest(BaseModel):
    graph: GraphRequest = Field(default_factory=GraphRequest)


class BacktestStudioRequest(BaseModel):
    symbol: str = Field(default="EURUSD", max_length=32)
    timeframe: str = Field(default="H1", max_length=16)
    count: int = Field(default=300, ge=50, le=2000)
    initial_balance: str = Field(default="10000")
    assumptions: dict[str, Any] = Field(default_factory=dict)
    graph: GraphRequest | None = None


class WalkForwardStudioRequest(BaseModel):
    symbol: str = Field(default="EURUSD", max_length=32)
    timeframe: str = Field(default="H1", max_length=16)
    count: int = Field(default=400, ge=100, le=5000)
    in_sample_bars: int = Field(default=120, ge=20, le=2000)
    out_of_sample_bars: int = Field(default=40, ge=10, le=1000)
    step_bars: int = Field(default=40, ge=5, le=1000)


class MarketplaceSaveRequest(BaseModel):
    name: str = Field(default="Untitled strategy", max_length=128)
    graph: GraphRequest = Field(default_factory=GraphRequest)
    assumptions: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=2000)
    strategy_id: str | None = None


class MarketplaceActionRequest(BaseModel):
    action: str = Field(description="clone|publish|favorite|compare|get")
    strategy_id: str
    other_id: str | None = None
    favorited: bool = True
    published: bool = True


@router.get("/workspace")
async def quant_studio_workspace(
    user: CurrentUser,
    studio: QuantStudioSvc,
) -> dict[str, Any]:
    return await studio.workspace(user_id=user.id)


@router.post("/builder/compile")
async def compile_builder(
    body: CompileRequest,
    user: CurrentUser,
    studio: QuantStudioSvc,
) -> dict[str, Any]:
    _ = user
    return studio.compile_graph(body.graph.model_dump())


@router.post("/backtest")
async def run_backtest_studio(
    body: BacktestStudioRequest,
    user: CurrentUser,
    studio: QuantStudioSvc,
) -> dict[str, Any]:
    return await studio.run_backtest_studio(
        user_id=user.id,
        symbol=body.symbol,
        timeframe=body.timeframe,
        count=body.count,
        initial_balance=body.initial_balance,
        assumptions=body.assumptions,
        graph=body.graph.model_dump() if body.graph else None,
    )


@router.post("/walkforward")
async def run_walkforward_studio(
    body: WalkForwardStudioRequest,
    user: CurrentUser,
    studio: QuantStudioSvc,
) -> dict[str, Any]:
    return await studio.run_walkforward_studio(
        user_id=user.id,
        symbol=body.symbol,
        timeframe=body.timeframe,
        count=body.count,
        in_sample_bars=body.in_sample_bars,
        out_of_sample_bars=body.out_of_sample_bars,
        step_bars=body.step_bars,
    )


@router.get("/portfolio-lab")
async def portfolio_lab(
    user: CurrentUser,
    studio: QuantStudioSvc,
) -> dict[str, Any]:
    return await studio.portfolio_lab(user_id=user.id)


@router.get("/live-monitor")
async def live_monitor(
    user: CurrentUser,
    studio: QuantStudioSvc,
) -> dict[str, Any]:
    return await studio.live_monitor(user_id=user.id)


@router.get("/marketplace")
async def marketplace_list(
    user: CurrentUser,
    studio: QuantStudioSvc,
) -> dict[str, Any]:
    return studio.marketplace_list(user.id)


@router.post("/marketplace/save")
async def marketplace_save(
    body: MarketplaceSaveRequest,
    user: CurrentUser,
    studio: QuantStudioSvc,
) -> dict[str, Any]:
    return studio.marketplace_save(
        user_id=user.id,
        name=body.name,
        graph=body.graph.model_dump(),
        assumptions=body.assumptions,
        notes=body.notes,
        strategy_id=body.strategy_id,
    )


@router.post("/marketplace/action")
async def marketplace_action(
    body: MarketplaceActionRequest,
    user: CurrentUser,
    studio: QuantStudioSvc,
) -> dict[str, Any]:
    return studio.marketplace_action(
        user_id=user.id,
        action=body.action,
        strategy_id=body.strategy_id,
        other_id=body.other_id,
        favorited=body.favorited,
        published=body.published,
    )


@router.get("/blocks")
async def list_blocks(
    user: CurrentUser,
) -> dict[str, Any]:
    from app.domain.quant_studio.visual_builder import BLOCK_CATALOG

    _ = user
    return {
        "status": "available",
        "items": BLOCK_CATALOG,
        "advisory_only": True,
        "autonomous_trading": False,
    }
