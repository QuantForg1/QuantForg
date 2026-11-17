"""Weltrade production API — Browser → Railway → Windows MT5 Gateway.

Additive; does not replace /mt5 or gateway REST.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

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


def _is_platform_operator(user: Any) -> bool:
    role = str(getattr(user, "role", "") or "").strip().lower()
    return role in {"owner", "admin"}


def _shared_terminal_operator_only(user: CurrentUser) -> None:
    """The platform terminal is one MT5 session shared by the platform.

    16-17 Nov 2026: a customer's restore-profile disconnected the owner's LIVE
    Weltrade session on it and logged it into the customer's XM account. Only
    the owner/admin may change that session; customer accounts are served by
    dedicated worker terminals.
    """
    if not _is_platform_operator(user):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "SHARED_TERMINAL_OWNER_ONLY",
                "message": (
                    "Your broker account is connected through a dedicated "
                    "QuantForg trading terminal, not the platform terminal. "
                    "Add it in Broker Accounts; it is assigned to a terminal "
                    "automatically."
                ),
            },
        )


_SHARED_TERMINAL_GUARD = [Depends(_shared_terminal_operator_only)]


@router.get("/profile")
async def weltrade_profile(_user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    return svc.profile()


@router.get("/health")
async def weltrade_health(user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    """Gateway / tunnel / MT5 session health for the Weltrade production desk."""
    return await svc.health(user_id=user.id, role=str(getattr(user, "role", "") or ""))


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
    if not _is_platform_operator(user):
        # Customers never touch the shared platform terminal: save the
        # account for a dedicated worker terminal instead.
        try:
            return await svc.register_customer_account(
                user_id=user.id,
                login=body.login,
                password=body.password or "",
                server=body.server,
                account_type=body.account_type,
                broker_slug=body.broker_slug,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_BROKER_ACCOUNT", "message": str(exc)},
            ) from exc
    try:
        return await svc.connect(
            user_id=user.id,
            login=body.login,
            password=body.password,
            server=body.server,
            account_type=body.account_type,
            broker_slug=body.broker_slug,
            prefer_attach=body.prefer_attach,
            path=body.path,
            confirm_leave_exposure=body.confirm_leave_exposure,
        )
    except Exception as exc:
        logger.warning(
            "weltrade_connect_failed",
            error_type=type(exc).__name__,
        )
        raise_trader_broker_failure(exc)


@router.post("/attach", dependencies=_SHARED_TERMINAL_GUARD)
async def weltrade_attach(
    body: WeltradeAttachRequest, user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    try:
        return await svc.attach(user_id=user.id, path=body.path)
    except Exception as exc:
        logger.warning("weltrade_attach_failed", error_type=type(exc).__name__)
        raise_trader_broker_failure(exc)


@router.post("/claim", dependencies=_SHARED_TERMINAL_GUARD)
async def weltrade_claim(user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    """Claim the verified terminal for this user. Gateway-online is not enough."""
    try:
        return await svc.claim_live_session(
            user_id=user.id, role=str(getattr(user, "role", "") or "")
        )
    except Exception as exc:
        logger.warning("weltrade_claim_failed", error_type=type(exc).__name__)
        raise_trader_broker_failure(exc)


@router.get("/exposure")
async def weltrade_exposure(user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    try:
        return await svc.exposure_for_user(
            user_id=user.id, role=str(getattr(user, "role", "") or "")
        )
    except Exception as exc:
        logger.warning("weltrade_exposure_failed", error_type=type(exc).__name__)
        raise_trader_broker_failure(exc)


@router.post("/disconnect")
async def weltrade_disconnect(user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    """Owner: drop the shared platform session. Customer: revoke saved account only."""
    if not _is_platform_operator(user):
        try:
            return await svc.disconnect_customer_account(user_id=user.id)
        except Exception as exc:
            logger.warning(
                "weltrade_customer_disconnect_failed",
                error_type=type(exc).__name__,
            )
            raise_trader_broker_failure(exc)
    return await svc.disconnect(user_id=user.id)


@router.post("/reconnect")
async def weltrade_reconnect(user: CurrentUser, svc: WeltradeSvc) -> dict[str, Any]:
    """Owner: reconnect shared terminal. Customer: re-queue worker assignment."""
    if not _is_platform_operator(user):
        try:
            return await svc.reconnect_customer_account(user_id=user.id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "CUSTOMER_RECONNECT_FAILED", "message": str(exc)},
            ) from exc
        except Exception as exc:
            logger.warning(
                "weltrade_customer_reconnect_failed",
                error_type=type(exc).__name__,
            )
            raise_trader_broker_failure(exc)
    try:
        return await svc.reconnect(user_id=user.id)
    except Exception as exc:
        logger.warning("weltrade_reconnect_failed", error_type=type(exc).__name__)
        raise_trader_broker_failure(exc)


@router.get("/runtime-profile")
async def weltrade_runtime_profile(
    user: CurrentUser, svc: WeltradeSvc
) -> dict[str, Any]:
    """Selected account for this user. Never includes a password or ciphertext."""
    profile = svc.load_persisted_broker_profile()
    store = svc._secret_store()
    if store is not None:
        selected = await store.public_selection(user_id=user.id)
        if selected is not None:
            profile = selected
    if isinstance(profile, dict):
        profile.pop("password", None)
        profile.pop("password_ciphertext", None)
        profile.pop("password_plaintext", None)
    return {"ok": True, "profile": profile}


@router.post("/restore-profile", dependencies=_SHARED_TERMINAL_GUARD)
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
