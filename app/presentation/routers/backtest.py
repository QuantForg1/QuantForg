"""Backtesting Engine API — offline simulation only.

Never calls order_send(). Never enables EXECUTION_ENABLED. Never live broker.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.application.dto.backtest import (
    BacktestBarCommand,
    GetBacktestCommand,
    ListBacktestsCommand,
    RunBacktestCommand,
)
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.backtest import (
    GetBacktestDep,
    ListBacktestsDep,
    RunBacktestDep,
)
from app.presentation.schemas.backtest import (
    BacktestListResponse,
    BacktestRunRequest,
    BacktestRunResponse,
    SimulatedTradeResponse,
)

router = APIRouter(prefix="/backtests", tags=["backtesting"])


def _to_response(dto: object) -> BacktestRunResponse:
    from app.application.dto.backtest import BacktestRunDTO

    assert isinstance(dto, BacktestRunDTO)
    return BacktestRunResponse(
        id=dto.id,
        request_id=dto.request_id,
        symbol=dto.symbol,
        timeframe=dto.timeframe,
        status=dto.status,
        replay_mode=dto.replay_mode,
        initial_balance=dto.initial_balance,
        metrics=dict(dto.metrics),
        equity_curve=list(dto.equity_curve),
        portfolio_snapshot=dict(dto.portfolio_snapshot),
        trades=[
            SimulatedTradeResponse(
                id=t.id,
                symbol=t.symbol,
                side=t.side,
                status=t.status,
                volume=t.volume,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                stop_loss=t.stop_loss,
                take_profit=t.take_profit,
                spread=t.spread,
                slippage=t.slippage,
                fees=t.fees,
                pnl=t.pnl,
                exit_reason=t.exit_reason,
                opened_at=t.opened_at,
                closed_at=t.closed_at,
            )
            for t in dto.trades
        ],
        trade_count=dto.trade_count,
        bar_count=dto.bar_count,
        replay_state=dict(dto.replay_state),
        assumptions=dict(dto.assumptions),
        error_message=dto.error_message,
        started_at=dto.started_at,
        finished_at=dto.finished_at,
    )


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest(
    body: BacktestRunRequest,
    request: Request,
    user: CurrentUser,
    run_uc: RunBacktestDep,
) -> BacktestRunResponse:
    """Run an offline backtest. Never places live trades."""
    ip, ua = get_client_meta(request)
    dto = await run_uc.execute(
        RunBacktestCommand(
            user_id=user.id,
            request_id=body.request_id,
            symbol=body.symbol,
            timeframe=body.timeframe,
            initial_balance=body.initial_balance,
            bars=tuple(
                BacktestBarCommand(
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
            ticks=tuple(body.ticks),
            replay_mode=body.replay_mode,
            spread=body.spread,
            slippage=body.slippage,
            fee_per_lot=body.fee_per_lot,
            lot_size=body.lot_size,
            stop_loss_distance=body.stop_loss_distance,
            take_profit_distance=body.take_profit_distance,
            auto_analysis=body.auto_analysis,
            max_open_trades=body.max_open_trades,
            consult_execution_safety=body.consult_execution_safety,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _to_response(dto)


@router.get("", response_model=BacktestListResponse)
async def list_backtests(
    user: CurrentUser,
    list_uc: ListBacktestsDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> BacktestListResponse:
    """List backtest runs for the current user."""
    dto = await list_uc.execute(ListBacktestsCommand(user_id=user.id, limit=limit))
    return BacktestListResponse(
        items=[_to_response(item) for item in dto.items],
        count=dto.count,
    )


@router.get("/{backtest_id}", response_model=BacktestRunResponse)
async def get_backtest(
    backtest_id: UUID,
    user: CurrentUser,
    get_uc: GetBacktestDep,
) -> BacktestRunResponse:
    """Get one backtest run with simulated trades and metrics."""
    dto = await get_uc.execute(
        GetBacktestCommand(user_id=user.id, backtest_id=backtest_id)
    )
    return _to_response(dto)
