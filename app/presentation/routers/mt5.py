"""MT5 connection + market-data REST API — no orders or live trading."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, Request

from app.application.dto.mt5 import (
    MT5ConnectCommand,
    MT5DisconnectCommand,
    MT5OrderValidateCommand,
)
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.mt5 import MT5Svc
from app.presentation.dto_mapping import dto_to_dict
from app.presentation.schemas.mt5 import (
    MT5AccountResponse,
    MT5CandleResponse,
    MT5ConnectionResponse,
    MT5ConnectRequest,
    MT5OrderCalculateResponse,
    MT5OrderValidateRequest,
    MT5OrderValidationResponse,
    MT5StatusResponse,
    MT5SymbolResponse,
    MT5TickResponse,
)

router = APIRouter(prefix="/mt5", tags=["mt5"])


@router.get("/status", response_model=MT5StatusResponse)
async def mt5_status(
    user: CurrentUser,
    mt5: MT5Svc,
) -> MT5StatusResponse:
    dto = await mt5.get_status.execute(user_id=user.id)
    return MT5StatusResponse(**dto_to_dict(dto))


@router.post("/connect", response_model=MT5ConnectionResponse)
async def mt5_connect(
    body: MT5ConnectRequest,
    request: Request,
    user: CurrentUser,
    mt5: MT5Svc,
) -> MT5ConnectionResponse:
    ip, ua = get_client_meta(request)
    dto = await mt5.connect.execute(
        MT5ConnectCommand(
            user_id=user.id,
            login=body.login,
            password=body.password,
            server=body.server,
            path=body.path,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return MT5ConnectionResponse(
        id=dto.id,
        user_id=dto.user_id,
        login=dto.login,
        server=dto.server,
        status=dto.status,
        connected=dto.connected,
        terminal_build=dto.terminal_build,
        terminal_version=dto.terminal_version,
        latency_ms=dto.latency_ms,
        last_heartbeat_at=dto.last_heartbeat_at,
        login_status=dto.login_status,
        session_ref=dto.session_ref,
        history=list(dto.history),
    )


@router.post("/disconnect", response_model=MT5StatusResponse)
async def mt5_disconnect(
    request: Request,
    user: CurrentUser,
    mt5: MT5Svc,
) -> MT5StatusResponse:
    ip, ua = get_client_meta(request)
    dto = await mt5.disconnect.execute(
        MT5DisconnectCommand(
            user_id=user.id,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return MT5StatusResponse(**dto_to_dict(dto))


@router.get("/account", response_model=MT5AccountResponse)
async def mt5_account(
    user: CurrentUser,
    mt5: MT5Svc,
) -> MT5AccountResponse:
    dto = await mt5.get_account.execute(user_id=user.id)
    return MT5AccountResponse(**dto_to_dict(dto))


@router.get("/symbols", response_model=list[MT5SymbolResponse])
async def mt5_symbols(
    user: CurrentUser,
    mt5: MT5Svc,
) -> list[MT5SymbolResponse]:
    items = await mt5.list_symbols.execute(user_id=user.id)
    return [MT5SymbolResponse(**dto_to_dict(i)) for i in items]


@router.get("/symbols/{symbol}", response_model=MT5SymbolResponse)
async def mt5_symbol_info(
    symbol: str,
    user: CurrentUser,
    mt5: MT5Svc,
) -> MT5SymbolResponse:
    dto = await mt5.get_symbol.execute(user_id=user.id, symbol=symbol)
    return MT5SymbolResponse(**dto_to_dict(dto))


@router.get("/ticks/{symbol}", response_model=MT5TickResponse)
async def mt5_latest_tick(
    symbol: str,
    user: CurrentUser,
    mt5: MT5Svc,
) -> MT5TickResponse:
    dto = await mt5.get_tick.execute(user_id=user.id, symbol=symbol)
    return MT5TickResponse(**dto_to_dict(dto))


@router.get("/candles/{symbol}", response_model=list[MT5CandleResponse])
async def mt5_candles(
    symbol: str,
    user: CurrentUser,
    mt5: MT5Svc,
    timeframe: str = Query(default="H1"),
    count: int = Query(default=100, ge=1, le=5000),
    start_pos: int | None = Query(default=None, ge=0),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> list[MT5CandleResponse]:
    items = await mt5.get_candles.execute(
        user_id=user.id,
        symbol=symbol,
        timeframe=timeframe,
        count=count,
        start_pos=start_pos,
        date_from=date_from,
        date_to=date_to,
    )
    return [MT5CandleResponse(**dto_to_dict(i)) for i in items]


@router.post("/order/validate", response_model=MT5OrderValidationResponse)
async def mt5_order_validate(
    body: MT5OrderValidateRequest,
    request: Request,
    user: CurrentUser,
    mt5: MT5Svc,
) -> MT5OrderValidationResponse:
    ip, ua = get_client_meta(request)
    dto = await mt5.validate_order.execute(
        MT5OrderValidateCommand(
            user_id=user.id,
            symbol=body.symbol,
            side=body.side,
            order_type=body.order_type,
            volume=body.volume,
            price=body.price,
            stop_loss=body.stop_loss,
            take_profit=body.take_profit,
            slippage=body.slippage,
            magic=body.magic,
            comment=body.comment,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return MT5OrderValidationResponse(
        id=dto.id,
        symbol=dto.symbol,
        side=dto.side,
        order_type=dto.order_type,
        volume=dto.volume,
        valid=dto.valid,
        retcode=dto.retcode,
        expected_margin=dto.expected_margin,
        estimated_profit=dto.estimated_profit,
        messages=list(dto.messages),
        checks=dict(dto.checks),
        request_snapshot=dict(dto.request_snapshot),
        validated_at=dto.validated_at,
    )


@router.post("/order/calculate", response_model=MT5OrderCalculateResponse)
async def mt5_order_calculate(
    body: MT5OrderValidateRequest,
    user: CurrentUser,
    mt5: MT5Svc,
) -> MT5OrderCalculateResponse:
    dto = await mt5.calculate_order.execute(
        MT5OrderValidateCommand(
            user_id=user.id,
            symbol=body.symbol,
            side=body.side,
            order_type=body.order_type,
            volume=body.volume,
            price=body.price,
            stop_loss=body.stop_loss,
            take_profit=body.take_profit,
            slippage=body.slippage,
            magic=body.magic,
            comment=body.comment,
        )
    )
    return MT5OrderCalculateResponse(
        symbol=dto.symbol,
        side=dto.side,
        order_type=dto.order_type,
        volume=dto.volume,
        price=dto.price,
        expected_margin=dto.expected_margin,
        estimated_profit=dto.estimated_profit,
        retcode=dto.retcode,
        messages=list(dto.messages),
        request_snapshot=dict(dto.request_snapshot),
    )
