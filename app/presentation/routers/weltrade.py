"""Weltrade production API — Browser → Railway → Windows MT5 Gateway.

Additive; does not replace /mt5 or gateway REST.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.weltrade import WeltradeSvc
from app.presentation.schemas.weltrade import (
    WeltradeAttachRequest,
    WeltradeConnectRequest,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/weltrade", tags=["weltrade"])


@router.get("/profile")
async def weltrade_profile(
    _user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    return svc.profile()


@router.get("/health")
async def weltrade_health(
    user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    """Gateway / tunnel / MT5 session health for the Weltrade production desk."""
    return await svc.health(user_id=user.id)


@router.get("/dashboard")
async def weltrade_dashboard(
    user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    return await svc.dashboard(user_id=user.id)


@router.post("/connect")
async def weltrade_connect(
    body: WeltradeConnectRequest, user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    _ = body.remember_on_gateway  # documented UX only — gateway always RAM-only
    try:
        return await svc.connect(
            user_id=user.id,
            login=body.login,
            password=body.password,
            server=body.server,
            account_type=body.account_type,
            prefer_attach=body.prefer_attach,
            path=body.path,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        logger.warning("weltrade_connect_http_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.post("/attach")
async def weltrade_attach(
    body: WeltradeAttachRequest, user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    try:
        return await svc.attach(user_id=user.id, path=body.path)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.post("/disconnect")
async def weltrade_disconnect(
    user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    return await svc.disconnect(user_id=user.id)


@router.post("/reconnect")
async def weltrade_reconnect(
    user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    try:
        return await svc.reconnect(user_id=user.id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
