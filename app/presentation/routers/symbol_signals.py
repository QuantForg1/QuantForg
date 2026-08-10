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


# --- Signal Intelligence v2 (read-only LIVE analytics) ---
# Registered before /signals/{symbol} so "intelligence" is not captured as a symbol.


@router.get("/signals/intelligence/overview")
async def si_overview(
    user: CurrentUser,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    _ = user
    from app.application.services import signal_intelligence_service as si

    return si.build_overview(days=days)


@router.get("/signals/intelligence/history")
async def si_history(
    user: CurrentUser,
    symbol: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    _ = user
    from app.application.services import signal_intelligence_service as si

    return si.list_signal_history(
        symbol=symbol, direction=direction, limit=limit, observe=True
    )


@router.get("/signals/intelligence/outcomes")
async def si_outcomes(
    user: CurrentUser,
    days: int = Query(default=14, ge=1, le=90),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    _ = user
    from app.application.services import signal_intelligence_service as si

    return si.build_outcomes(days=days, limit=limit)


@router.get("/signals/intelligence/probability")
async def si_probability(user: CurrentUser) -> dict[str, Any]:
    _ = user
    from app.application.services import signal_intelligence_service as si

    return si.build_probabilities()


@router.get("/signals/intelligence/heatmap")
async def si_heatmap(user: CurrentUser) -> dict[str, Any]:
    _ = user
    from app.application.services import signal_intelligence_service as si

    return si.build_heatmap()


@router.get("/signals/intelligence/analytics")
async def si_analytics(
    user: CurrentUser,
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    _ = user
    from app.application.services import signal_intelligence_service as si

    return si.build_symbol_analytics(days=days)


@router.get("/signals/intelligence/chart-markers/{symbol}")
async def si_chart_markers(
    symbol: str,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    from app.application.services import signal_intelligence_service as si

    return si.chart_markers(symbol, limit=limit)


@router.post("/signals/intelligence/observe")
async def si_observe(user: OperatorUser) -> dict[str, Any]:
    """Owner/Admin — snapshot current LIVE scan into signal_history."""
    _ = user
    from app.application.services import signal_intelligence_service as si

    return si.observe_live_scan()


class SyntheticSignalOnceBody(BaseModel):
    symbol: str = "XAUUSD"
    side: str = "BUY"
    confirmed: bool = False
    restore_previous: bool = True


@router.get("/signals/test/synthetic-once/status")
async def synthetic_signal_once_status(user: OperatorUser) -> dict[str, Any]:
    """Owner/Admin — one-shot TEST/SYNTHETIC inject status (never executes)."""
    _ = user
    from app.application.services import synthetic_signal_once as sso

    return sso.status()


@router.post("/signals/test/synthetic-once/arm")
async def synthetic_signal_once_arm(
    body: SyntheticSignalOnceBody,
    user: OperatorUser,
) -> dict[str, Any]:
    """Owner/Admin — arm exactly one pending TEST inject (never executes)."""
    _ = user
    from app.application.services import synthetic_signal_once as sso

    result = sso.arm_once(confirmed=body.confirmed)
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error") or "rejected")
    return result


@router.post("/signals/test/synthetic-once")
async def synthetic_signal_once_inject(
    body: SyntheticSignalOnceBody,
    user: OperatorUser,
) -> dict[str, Any]:
    """Owner/Admin — inject exactly one TEST/SYNTHETIC Signal Center row.

    Monitoring projection only. Never OMS. Never MT5 order_send.
    Auto-disarms after one successful inject.
    """
    _ = user
    from app.application.services import synthetic_signal_once as sso

    side = "SELL" if body.side.strip().upper() == "SELL" else "BUY"
    result = sso.inject_once(
        symbol=body.symbol,
        side=side,  # type: ignore[arg-type]
        confirmed=body.confirmed,
        restore_previous=body.restore_previous,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error") or "rejected")
    return result


@router.get("/signals/{symbol}")
async def get_signal_detail(symbol: str, user: CurrentUser) -> dict[str, Any]:
    _ = user
    if symbol.strip().lower() == "intelligence":
        raise HTTPException(status_code=404, detail="Use /signals/intelligence/*")
    if symbol.strip().lower() == "test":
        raise HTTPException(status_code=404, detail="Use /signals/test/synthetic-once")
    item = signal_center_service.get_signal(symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return item
