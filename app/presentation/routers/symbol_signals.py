"""Symbol Management + Signal Center APIs — UI/Settings only."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.application.services import signal_center_service, symbol_management_service
from app.domain.enums.user import UserRole
from app.domain.institutional_trading.operations.control_plane import (
    PermissionDenied,
)
from app.domain.institutional_trading.operations.models import OperatorIdentity
from app.presentation.dependencies.auth import CurrentUser, require_roles

router = APIRouter(tags=["symbol-management", "signals"])

OperatorUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


def _operator(
    user: AuthUserDTO,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> OperatorIdentity:
    ip = x_forwarded_for or (request.client.host if request.client else None)
    ua = request.headers.get("user-agent")
    return OperatorIdentity(
        user_id=user.id,
        role=str(user.role).strip().lower(),
        display_name=user.display_name or user.email or str(user.id),
        ip=ip,
        user_agent=ua,
    )


class SymbolUpdateBody(BaseModel):
    enabled: bool | None = None
    favorite: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=10_000)
    notes: str | None = None
    asset_class: str | None = None
    reason: str = Field(default="symbol_management_update", min_length=1)
    confirmed: bool = True


class SymbolBulkBody(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    enable: bool | None = None
    favorite: bool | None = None
    priorities: dict[str, int] | None = None
    reason: str = Field(default="symbol_management_bulk", min_length=1)
    confirmed: bool = True


class SymbolReorderBody(BaseModel):
    ordered_symbols: list[str] = Field(min_length=1)
    reason: str = Field(default="symbol_management_reorder", min_length=1)
    confirmed: bool = True


@router.get("/symbols")
async def get_symbols(
    user: CurrentUser,
    q: str = Query(default=""),
    asset_class: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    favorites: bool = Query(default=False),
) -> dict[str, Any]:
    """List broker symbols merged with operator Symbol Management prefs."""
    _ = user
    return symbol_management_service.list_managed_symbols(
        q=q,
        asset_class=asset_class,
        enabled=enabled,
        favorites_only=favorites,
    )


@router.get("/symbols/{symbol}")
async def get_symbol(symbol: str, user: CurrentUser) -> dict[str, Any]:
    _ = user
    payload = symbol_management_service.list_managed_symbols(q=symbol)
    for item in payload.get("items") or []:
        if str(item.get("symbol") or "").upper() == symbol.strip().upper():
            return item
    raise HTTPException(status_code=404, detail="Symbol not found")


@router.put("/symbols/{symbol}")
async def put_symbol(
    symbol: str,
    body: SymbolUpdateBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmed must be true")
    op = _operator(user, request, x_forwarded_for)
    try:
        row = symbol_management_service.update_symbol(
            symbol,
            enabled=body.enabled,
            favorite=body.favorite,
            priority=body.priority,
            notes=body.notes,
            asset_class=body.asset_class,
            updated_by=user.id,
            operator=op,
            sync_plane=True,
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "symbol": row}


@router.post("/symbols/bulk")
async def post_symbols_bulk(
    body: SymbolBulkBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmed must be true")
    op = _operator(user, request, x_forwarded_for)
    try:
        result = symbol_management_service.bulk_update(
            symbols=body.symbols,
            enable=body.enable,
            favorite=body.favorite,
            priorities=body.priorities,
            updated_by=user.id,
            operator=op,
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **result}


@router.post("/symbols/reorder")
async def post_symbols_reorder(
    body: SymbolReorderBody,
    user: OperatorUser,
    request: Request,
    x_forwarded_for: str | None = Header(default=None),
) -> dict[str, Any]:
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="confirmed must be true")
    op = _operator(user, request, x_forwarded_for)
    try:
        result = symbol_management_service.reorder_priorities(
            body.ordered_symbols,
            updated_by=user.id,
            operator=op,
        )
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"ok": True, **result}


@router.get("/signals")
async def get_signals(
    user: CurrentUser,
    q: str = Query(default=""),
    direction: str | None = Query(default=None),
    asset_class: str | None = Query(default=None),
    strong_only: bool = Query(default=False),
    high_confidence: bool = Query(default=False),
    enabled_only: bool = Query(default=True),
) -> dict[str, Any]:
    """LIVE Signal Center feed from existing AI multi-asset scan."""
    _ = user
    return signal_center_service.list_live_signals(
        q=q,
        direction=direction,
        asset_class=asset_class,
        strong_only=strong_only,
        high_confidence=high_confidence,
        enabled_only=enabled_only,
    )


@router.get("/signals/{symbol}")
async def get_signal_detail(symbol: str, user: CurrentUser) -> dict[str, Any]:
    _ = user
    item = signal_center_service.get_signal(symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return item
