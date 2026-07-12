"""Strategy Runtime API — decisions only, never order_send / never enable execution."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.application.dto.strategy_runtime import (
    ListStrategySignalsCommand,
    StrategyEvaluateCommand,
)
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.strategy import (
    EvaluateStrategyDep,
    ListStrategySignalsDep,
)
from app.presentation.schemas.strategy import (
    StrategyEvaluateRequest,
    StrategyEvaluateResponse,
    StrategySignalListResponse,
    StrategySignalResponse,
)

router = APIRouter(prefix="/strategy", tags=["strategy-runtime"])


@router.post("/evaluate", response_model=StrategyEvaluateResponse)
async def strategy_evaluate(
    body: StrategyEvaluateRequest,
    request: Request,
    user: CurrentUser,
    evaluate: EvaluateStrategyDep,
) -> StrategyEvaluateResponse:
    """Run the Strategy Runtime pipeline.

    Returns NO_ACTION | WATCH | READY | BLOCKED. Never places an order.
    Never enables EXECUTION_ENABLED. Never calls order_send().
    """
    ip, ua = get_client_meta(request)
    dto = await evaluate.execute(
        StrategyEvaluateCommand(
            user_id=user.id,
            request_id=body.request_id,
            symbol=body.symbol,
            timeframe=body.timeframe,
            market_open=body.market_open,
            session=body.session,
            structure_bias=body.structure_bias,
            liquidity_sweep_bullish=body.liquidity_sweep_bullish,
            liquidity_sweep_bearish=body.liquidity_sweep_bearish,
            order_block_bullish=body.order_block_bullish,
            order_block_bearish=body.order_block_bearish,
            fvg_bullish=body.fvg_bullish,
            fvg_bearish=body.fvg_bearish,
            has_structure=body.has_structure,
            has_liquidity=body.has_liquidity,
            has_order_blocks=body.has_order_blocks,
            has_fvgs=body.has_fvgs,
            analysis_notes=tuple(body.analysis_notes),
            check_risk=body.check_risk,
            requested_lots=body.requested_lots,
            stop_loss_distance=body.stop_loss_distance,
            entry_price=body.entry_price,
            equity=body.equity,
            balance=body.balance,
            tick_age_seconds=body.tick_age_seconds,
            candle_count=body.candle_count,
            last_price=body.last_price,
            ip_address=ip,
            user_agent=ua,
        )
    )
    signal = None
    if dto.signal is not None:
        signal = StrategySignalResponse(
            id=dto.signal.id,
            symbol=dto.signal.symbol,
            timeframe=dto.signal.timeframe,
            direction=dto.signal.direction,
            confidence=dto.signal.confidence,
            reasons=list(dto.signal.reasons),
            generated_at=dto.signal.generated_at,
            evaluation_id=dto.signal.evaluation_id,
            rejected=dto.signal.rejected,
            rejection_reasons=list(dto.signal.rejection_reasons),
        )
    return StrategyEvaluateResponse(
        id=dto.id,
        request_id=dto.request_id,
        symbol=dto.symbol,
        timeframe=dto.timeframe,
        decision=dto.decision,
        reasons=list(dto.reasons),
        preconditions=dict(dto.preconditions),
        market_state=dict(dto.market_state),
        signal=signal,
        risk_decision=dto.risk_decision,
        risk_score=dto.risk_score,
        evaluated_at=dto.evaluated_at,
    )


@router.get("/signals", response_model=StrategySignalListResponse)
async def strategy_signals(
    user: CurrentUser,
    list_signals: ListStrategySignalsDep,
    limit: int = Query(default=50, ge=1, le=200),
    include_rejected: bool = Query(default=True),
) -> StrategySignalListResponse:
    """List Strategy Runtime signals for the current user (history only)."""
    dto = await list_signals.execute(
        ListStrategySignalsCommand(
            user_id=user.id,
            limit=limit,
            include_rejected=include_rejected,
        )
    )
    return StrategySignalListResponse(
        items=[
            StrategySignalResponse(
                id=s.id,
                symbol=s.symbol,
                timeframe=s.timeframe,
                direction=s.direction,
                confidence=s.confidence,
                reasons=list(s.reasons),
                generated_at=s.generated_at,
                evaluation_id=s.evaluation_id,
                rejected=s.rejected,
                rejection_reasons=list(s.rejection_reasons),
            )
            for s in dto.items
        ],
        count=dto.count,
    )
