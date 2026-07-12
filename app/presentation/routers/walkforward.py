"""Walk-Forward Validation API — offline only.

Never calls order_send(). Never enables EXECUTION_ENABLED. Never live trades.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.application.dto.walkforward import (
    GetWalkForwardCommand,
    ListWalkForwardCommand,
    RunWalkForwardCommand,
    WalkForwardBarCommand,
    WalkForwardRunDTO,
)
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.walkforward import (
    GetWalkForwardDep,
    ListWalkForwardDep,
    RunWalkForwardDep,
)
from app.presentation.schemas.walkforward import (
    WalkForwardListResponse,
    WalkForwardRunRequest,
    WalkForwardRunResponse,
)

router = APIRouter(prefix="/walkforward", tags=["walk-forward"])


def _to_response(dto: WalkForwardRunDTO) -> WalkForwardRunResponse:
    return WalkForwardRunResponse(
        id=dto.id,
        request_id=dto.request_id,
        symbol=dto.symbol,
        timeframe=dto.timeframe,
        status=dto.status,
        promotion=dto.promotion,
        window_config=dict(dto.window_config),
        folds=list(dto.folds),
        aggregated_is=dict(dto.aggregated_is),
        aggregated_oos=dict(dto.aggregated_oos),
        robustness=dict(dto.robustness),
        combined_equity=list(dto.combined_equity),
        report=dict(dto.report),
        bar_count=dto.bar_count,
        fold_count=dto.fold_count,
        error_message=dto.error_message,
        started_at=dto.started_at,
        finished_at=dto.finished_at,
    )


@router.post("/run", response_model=WalkForwardRunResponse)
async def run_walkforward(
    body: WalkForwardRunRequest,
    request: Request,
    user: CurrentUser,
    run_uc: RunWalkForwardDep,
) -> WalkForwardRunResponse:
    """Run walk-forward validation (IS backtest + OOS aggregate)."""
    ip, ua = get_client_meta(request)
    dto = await run_uc.execute(
        RunWalkForwardCommand(
            user_id=user.id,
            request_id=body.request_id,
            symbol=body.symbol,
            timeframe=body.timeframe,
            initial_balance=body.initial_balance,
            bars=tuple(
                WalkForwardBarCommand(
                    open_time=b.open_time,
                    open=b.open,
                    high=b.high,
                    low=b.low,
                    close=b.close,
                    volume=b.volume,
                    close_time=b.close_time,
                )
                for b in body.bars
            ),
            in_sample_bars=body.in_sample_bars,
            out_of_sample_bars=body.out_of_sample_bars,
            step_bars=body.step_bars,
            anchored=body.anchored,
            optimize_params=body.optimize_params,
            auto_analysis=body.auto_analysis,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _to_response(dto)


@router.get("/results", response_model=WalkForwardListResponse)
async def list_walkforward_results(
    user: CurrentUser,
    list_uc: ListWalkForwardDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> WalkForwardListResponse:
    """List walk-forward validation results for the current user."""
    dto = await list_uc.execute(ListWalkForwardCommand(user_id=user.id, limit=limit))
    return WalkForwardListResponse(
        items=[_to_response(item) for item in dto.items],
        count=dto.count,
    )


@router.get("/{run_id}", response_model=WalkForwardRunResponse)
async def get_walkforward(
    run_id: UUID,
    user: CurrentUser,
    get_uc: GetWalkForwardDep,
) -> WalkForwardRunResponse:
    """Get one walk-forward validation run with IS/OOS report."""
    dto = await get_uc.execute(GetWalkForwardCommand(user_id=user.id, run_id=run_id))
    return _to_response(dto)
