"""Strategy Runtime API — decisions only, never order_send / never enable execution.

Additive Strategy Engine endpoints live under /strategy/engine/* and catalog.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.application.dto.strategy_runtime import (
    ListStrategySignalsCommand,
    StrategyEvaluateCommand,
)
from app.application.services.strategy_engine import StrategyAllocation
from app.domain.interfaces.strategy_engine import OhlcBar, StrategyRiskLimits
from app.domain.market_data.timeframe import Timeframe
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.strategy import (
    EvaluateStrategyDep,
    ListStrategySignalsDep,
    get_market_data,
)
from app.presentation.dependencies.strategy_engine import StrategyEngineDep
from app.presentation.schemas.strategy import (
    StrategyAllocationPutRequest,
    StrategyEngineRunRequest,
    StrategyEngineValidateRequest,
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


@router.get("/catalog")
async def strategy_catalog(
    user: CurrentUser,
    engine: StrategyEngineDep,
) -> dict[str, Any]:
    """List deterministic Strategy Engine plugins (not ICT runtime)."""
    _ = user
    items = engine.catalog()
    return {"items": items, "count": len(items)}


@router.post("/engine/validate")
async def strategy_engine_validate(
    body: StrategyEngineValidateRequest,
    user: CurrentUser,
    engine: StrategyEngineDep,
) -> dict[str, Any]:
    """Validate strategy params / rule tree before run."""
    _ = user
    return engine.validate_rules(body.strategy_key, body.params)


@router.post("/engine/run")
async def strategy_engine_run(
    body: StrategyEngineRunRequest,
    user: CurrentUser,
    engine: StrategyEngineDep,
) -> dict[str, Any]:
    """Run a deterministic strategy plugin → BUY/SELL/EXIT/HOLD + explainability.

    Never places trades. Never enables EXECUTION_ENABLED.
    Bars must be supplied or loaded from MT5 — never fabricated.
    """
    _ = user
    bars: list[OhlcBar] = [
        OhlcBar(
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume,
            time=b.time,
        )
        for b in body.bars
    ]
    bar_source = "request"
    if not bars and body.use_mt5_bars:
        market = get_market_data()
        if market is None:
            raise HTTPException(
                status_code=400,
                detail="No bars supplied and MT5 market data unavailable",
            )
        try:
            tf = Timeframe.parse(body.timeframe)
            candles = market.historical_candles(
                body.symbol, tf, count=body.mt5_bar_count
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to load MT5 candles: {exc}",
            ) from exc
        bars = [
            OhlcBar(
                open=float(c.open),
                high=float(c.high),
                low=float(c.low),
                close=float(c.close),
                volume=float(c.tick_volume),
                time=c.open_time.isoformat(),
            )
            for c in candles
        ]
        bar_source = "mt5"
        if not bars:
            raise HTTPException(
                status_code=400,
                detail="MT5 returned no candles (refusing fabricated bars)",
            )

    limits = None
    if body.limits is not None:
        limits = StrategyRiskLimits(
            max_risk_pct=body.limits.max_risk_pct,
            max_trades=body.limits.max_trades,
            daily_loss_pct=body.limits.daily_loss_pct,
            max_exposure_pct=body.limits.max_exposure_pct,
            max_correlation=body.limits.max_correlation,
        )

    result = engine.run(
        strategy_key=body.strategy_key,
        symbol=body.symbol,
        timeframe=body.timeframe,
        bars=bars,
        params=body.params,
        session=body.session,
        market_state=body.market_state,
        open_trades=body.open_trades,
        daily_pnl_pct=body.daily_pnl_pct,
        exposure_pct=body.exposure_pct,
        correlation=body.correlation,
        limits=limits,
        allocation_weight_pct=body.allocation_weight_pct,
    )
    result["bar_source"] = bar_source
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "run failed")
    return result


@router.get("/portfolio")
async def strategy_portfolio(
    user: CurrentUser,
    engine: StrategyEngineDep,
) -> dict[str, Any]:
    """Strategy allocation + performance pointers (no invented PnL)."""
    _ = user
    return engine.portfolio_summary()


@router.put("/portfolio/allocations")
async def strategy_set_allocations(
    body: StrategyAllocationPutRequest,
    user: CurrentUser,
    engine: StrategyEngineDep,
) -> dict[str, Any]:
    """Set in-memory strategy allocation weights (session process scope)."""
    _ = user
    try:
        items = [
            StrategyAllocation(
                strategy_key=a.strategy_key,
                weight_pct=a.weight_pct,
                symbols=tuple(s.upper() for s in a.symbols),
            )
            for a in body.allocations
        ]
        allocations = engine.set_allocations(items)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"allocations": allocations, "count": len(allocations)}
