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
from app.presentation.routers.weltrade import (
    _SHARED_TERMINAL_GUARD as SHARED_TERMINAL_GUARD,
)
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
    MT5SymbolsPageResponse,
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


@router.post(
    "/connect", response_model=MT5ConnectionResponse, dependencies=SHARED_TERMINAL_GUARD
)
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


@router.post(
    "/disconnect", response_model=MT5StatusResponse, dependencies=SHARED_TERMINAL_GUARD
)
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


@router.get("/symbols", response_model=MT5SymbolsPageResponse)
async def mt5_symbols(
    user: CurrentUser,
    mt5: MT5Svc,
    q: str = Query(default="", max_length=64),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    include_quotes: bool = Query(default=False),
) -> MT5SymbolsPageResponse:
    page = await mt5.list_symbols.execute(
        user_id=user.id,
        q=q,
        offset=offset,
        limit=limit,
        include_quotes=include_quotes,
    )
    return MT5SymbolsPageResponse(
        items=[MT5SymbolResponse(**dto_to_dict(i)) for i in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
        has_more=page.has_more,
    )


@router.get("/gold-mapping")
async def mt5_gold_mapping(user: CurrentUser, mt5: MT5Svc) -> dict[str, object]:
    """Gold First: canonical XAUUSD -> this user's broker symbol (read-only).

    Uses the caller's own live MT5 session only (the use cases enforce
    ownership). The symbol is mapped only after its live MT5 metadata
    validates as spot gold in USD; MISSING / AMBIGUOUS / INVALID are reported
    as such and execution fails closed on them.
    """
    from app.domain.trading.gold_instrument_mapping import (
        discovery_hint_codes,
        is_gold_candidate,
        resolve_gold_mapping,
    )

    account = await mt5.get_account.execute(user_id=user.id)
    acct = dto_to_dict(account)
    broker_label = str(acct.get("company") or acct.get("server") or "")
    codes: list[str] = []
    for q in ("XAU", "GOLD"):
        page = await mt5.list_symbols.execute(
            user_id=user.id, q=q, offset=0, limit=50, include_quotes=False
        )
        for item in page.items:
            if is_gold_candidate(item.code, getattr(item, "description", "")):
                if item.code not in codes:
                    codes.append(item.code)
    # Broker spelling hints expand discovery only — never VALIDATED by name.
    for hint in discovery_hint_codes(broker_label):
        if hint not in codes:
            codes.append(hint)
    specs = []
    for code in codes[:12]:
        try:
            dto = await mt5.get_symbol.execute(user_id=user.id, symbol=code)
        except Exception:
            continue
        row = dto_to_dict(dto)
        if is_gold_candidate(
            str(row.get("code") or code), str(row.get("description") or "")
        ):
            specs.append(row)
    mapping = resolve_gold_mapping(
        specs,
        broker=broker_label,
        server=str(acct.get("server") or "") or None,
        login=acct.get("login"),
        account_currency=str(acct.get("currency") or "") or None,
        discovery_source="mt5_symbol_info+broker_hints",
    )
    return mapping.as_dict()


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


@router.get("/research/ticks/{symbol}", response_model=MT5TickResponse)
async def mt5_research_tick(
    symbol: str,
    user: CurrentUser,
    mt5: MT5Svc,
) -> MT5TickResponse:
    """Public gold market tick from the platform feed (no customer MT5 ownership)."""
    _ = user
    dto = await mt5.get_research_tick.execute(symbol=symbol)
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


@router.get("/research/candles/{symbol}", response_model=list[MT5CandleResponse])
async def mt5_research_candles(
    symbol: str,
    user: CurrentUser,
    mt5: MT5Svc,
    timeframe: str = Query(default="H1"),
    count: int = Query(default=100, ge=1, le=5000),
    start_pos: int | None = Query(default=None, ge=0),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> list[MT5CandleResponse]:
    """Public gold candles from the platform feed (no customer MT5 ownership)."""
    _ = user
    items = await mt5.get_research_candles.execute(
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
            request_id=body.request_id,
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
