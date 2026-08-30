"""Weltrade production API — Browser → Railway → Windows MT5 Gateway.

Additive; does not replace /mt5 or gateway REST.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.domain.exceptions.base import NotFoundError
from app.presentation.broker_trader_errors import raise_trader_broker_failure
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
async def weltrade_profile(_user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    return svc.profile()


@router.get("/health")
async def weltrade_health(user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    """Gateway / tunnel / MT5 session health for the Weltrade production desk."""
    return await svc.health(
        user_id=user.id, role=str(getattr(user, "role", "") or "")
    )


@router.get("/dashboard")
async def weltrade_dashboard(user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    return await svc.dashboard(
        user_id=user.id, role=str(getattr(user, "role", "") or "")
    )


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
    except Exception as exc:
        logger.warning(
            "weltrade_connect_failed",
            error_type=type(exc).__name__,
        )
        raise_trader_broker_failure(exc)


@router.post("/attach")
async def weltrade_attach(
    body: WeltradeAttachRequest, user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    try:
        return await svc.attach(user_id=user.id, path=body.path)
    except Exception as exc:
        logger.warning("weltrade_attach_failed", error_type=type(exc).__name__)
        raise_trader_broker_failure(exc)


@router.post("/disconnect")
async def weltrade_disconnect(user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    return await svc.disconnect(user_id=user.id)


@router.post("/reconnect")
async def weltrade_reconnect(user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    try:
        return await svc.reconnect(user_id=user.id)
    except Exception as exc:
        logger.warning("weltrade_reconnect_failed", error_type=type(exc).__name__)
        raise_trader_broker_failure(exc)


@router.get("/runtime-profile")
async def weltrade_runtime_profile(
    _user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    """Public broker restore profile (never includes password/ciphertext)."""
    profile = svc.load_persisted_broker_profile()
    return {"ok": True, "profile": profile}


@router.post("/restore-profile")
async def weltrade_restore_profile(
    user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    """Restore broker session from encrypted local profile after restart."""
    try:
        result = await svc.restore_from_persisted_profile(user_id=user.id)
        if result is None:
            raise NotFoundError(
                "Connect your broker account to start.",
                code="BROKER_NOT_CONNECTED",
                details={"reason": "BROKER_NOT_CONNECTED"},
            )
        result["restored_from_profile"] = True
        return result
    except NotFoundError:
        raise
    except Exception as exc:
        logger.warning(
            "weltrade_restore_profile_failed",
            error_type=type(exc).__name__,
        )
        raise_trader_broker_failure(exc)
