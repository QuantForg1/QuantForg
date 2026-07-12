"""Paper Trading API — live market data, simulated fills only.

Never calls order_send(). Never enables EXECUTION_ENABLED.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.application.dto.paper import (
    ListPaperPositionsCommand,
    PaperHistoryCommand,
    PaperPerformanceCommand,
    PlacePaperOrderCommand,
)
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.paper import (
    ListPaperPositionsDep,
    PaperHistoryDep,
    PaperPerformanceDep,
    PlacePaperOrderDep,
)
from app.presentation.schemas.paper import (
    PaperHistoryResponse,
    PaperOrderResponse,
    PaperPerformanceResponse,
    PaperPositionListResponse,
    PaperPositionResponse,
    PaperTradeResponse,
    PlacePaperOrderRequest,
    PlacePaperOrderResponse,
)

router = APIRouter(prefix="/paper", tags=["paper-trading"])


def _order_resp(dto: object) -> PaperOrderResponse:
    from app.application.dto.paper import PaperOrderDTO

    assert isinstance(dto, PaperOrderDTO)
    return PaperOrderResponse(
        id=dto.id,
        symbol=dto.symbol,
        side=dto.side,
        order_type=dto.order_type,
        volume=dto.volume,
        status=dto.status,
        requested_price=dto.requested_price,
        fill_price=dto.fill_price,
        filled_volume=dto.filled_volume,
        stop_loss=dto.stop_loss,
        take_profit=dto.take_profit,
        spread=dto.spread,
        slippage=dto.slippage,
        commission=dto.commission,
        rejection_reason=dto.rejection_reason,
        position_id=dto.position_id,
        client_order_id=dto.client_order_id,
        submitted_at=dto.submitted_at,
        filled_at=dto.filled_at,
    )


def _position_resp(dto: object) -> PaperPositionResponse:
    from app.application.dto.paper import PaperPositionDTO

    assert isinstance(dto, PaperPositionDTO)
    return PaperPositionResponse(
        id=dto.id,
        symbol=dto.symbol,
        side=dto.side,
        status=dto.status,
        volume=dto.volume,
        remaining_volume=dto.remaining_volume,
        entry_price=dto.entry_price,
        current_price=dto.current_price,
        stop_loss=dto.stop_loss,
        take_profit=dto.take_profit,
        floating_pnl=dto.floating_pnl,
        realized_pnl=dto.realized_pnl,
        commission=dto.commission,
        opened_at=dto.opened_at,
        closed_at=dto.closed_at,
    )


def _trade_resp(dto: object) -> PaperTradeResponse:
    from app.application.dto.paper import PaperTradeDTO

    assert isinstance(dto, PaperTradeDTO)
    return PaperTradeResponse(
        id=dto.id,
        symbol=dto.symbol,
        side=dto.side,
        volume=dto.volume,
        entry_price=dto.entry_price,
        exit_price=dto.exit_price,
        pnl=dto.pnl,
        commission=dto.commission,
        spread=dto.spread,
        slippage=dto.slippage,
        opened_at=dto.opened_at,
        closed_at=dto.closed_at,
    )


@router.post("/orders", response_model=PlacePaperOrderResponse)
async def place_paper_order(
    body: PlacePaperOrderRequest,
    request: Request,
    user: CurrentUser,
    place: PlacePaperOrderDep,
) -> PlacePaperOrderResponse:
    """Place a paper order against live MT5 quotes (simulated fill only)."""
    ip, ua = get_client_meta(request)
    dto = await place.execute(
        PlacePaperOrderCommand(
            user_id=user.id,
            symbol=body.symbol,
            side=body.side,
            order_type=body.order_type,
            volume=body.volume,
            price=body.price,
            stop_loss=body.stop_loss,
            take_profit=body.take_profit,
            client_order_id=body.client_order_id,
            reduce_position_id=body.reduce_position_id,
            initial_balance=body.initial_balance,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return PlacePaperOrderResponse(
        order=_order_resp(dto.order),
        position=_position_resp(dto.position) if dto.position else None,
        trade=_trade_resp(dto.trade) if dto.trade else None,
        portfolio=dict(dto.portfolio),
        quote=dict(dto.quote),
    )


@router.get("/positions", response_model=PaperPositionListResponse)
async def list_paper_positions(
    user: CurrentUser,
    list_uc: ListPaperPositionsDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> PaperPositionListResponse:
    """List open paper positions (marked to live MT5 quotes)."""
    dto = await list_uc.execute(ListPaperPositionsCommand(user_id=user.id, limit=limit))
    return PaperPositionListResponse(
        items=[_position_resp(p) for p in dto.items],
        count=dto.count,
        portfolio=dict(dto.portfolio),
    )


@router.get("/history", response_model=PaperHistoryResponse)
async def paper_history(
    user: CurrentUser,
    history: PaperHistoryDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> PaperHistoryResponse:
    """Paper order / trade / position history."""
    dto = await history.execute(PaperHistoryCommand(user_id=user.id, limit=limit))
    return PaperHistoryResponse(
        orders=[_order_resp(o) for o in dto.orders],
        trades=[_trade_resp(t) for t in dto.trades],
        positions=[_position_resp(p) for p in dto.positions],
    )


@router.get("/performance", response_model=PaperPerformanceResponse)
async def paper_performance(
    user: CurrentUser,
    perf: PaperPerformanceDep,
) -> PaperPerformanceResponse:
    """Paper portfolio performance snapshot."""
    dto = await perf.execute(PaperPerformanceCommand(user_id=user.id))
    return PaperPerformanceResponse(
        performance=dict(dto.performance),
        portfolio=dict(dto.portfolio),
    )
