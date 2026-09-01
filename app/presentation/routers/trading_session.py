"""Authenticated trading session — status and owned-account robot control.

Does not duplicate ITE ops. Robot mutations require an owned live broker
connection. Traders may control their own account robot (CONTROL_OWN_ROBOT).
Owner/admin global kill-switch and mode remain on /ite/ops.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from app.application.services.trading_session import (
    ControlTradingRobotUseCase,
    GetTradingSessionUseCase,
)
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.mt5 import get_mt5_adapter, get_mt5_uow_factory
from app.presentation.dependencies.weltrade import WeltradeSvc
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/trading", tags=["trading-session"])


def _session_uc() -> GetTradingSessionUseCase:
    return GetTradingSessionUseCase(
        uow_factory=get_mt5_uow_factory(),
        adapter=get_mt5_adapter(),
    )


def _control_uc() -> ControlTradingRobotUseCase:
    return ControlTradingRobotUseCase(
        uow_factory=get_mt5_uow_factory(),
        adapter=get_mt5_adapter(),
    )


@router.get("/session")
async def get_trading_session(
    user: CurrentUser, weltrade: WeltradeSvc
) -> dict[str, object]:
    # Owner/admin adopt after Railway redeploy loses ephemeral profile/DB bind.
    # Best-effort: a bind failure must not 500 the whole workspace.
    try:
        await asyncio.wait_for(
            weltrade.ensure_user_session_bound(
                user_id=user.id, role=str(getattr(user, "role", "") or "")
            ),
            timeout=4.0,
        )
    except TimeoutError:
        logger.warning(
            "trading_session_bind_timeout",
            user_id=str(user.id),
        )
    except Exception as exc:
        logger.warning(
            "trading_session_bind_failed",
            user_id=str(user.id),
            error=str(exc),
        )
    return await _session_uc().execute(user_id=user.id)


@router.get("/account")
async def get_trading_account(
    user: CurrentUser, weltrade: WeltradeSvc
) -> dict[str, object]:
    await weltrade.ensure_user_session_bound(
        user_id=user.id, role=str(getattr(user, "role", "") or "")
    )
    return await _session_uc().execute(user_id=user.id)


@router.get("/robot/status")
async def get_robot_status(
    user: CurrentUser, weltrade: WeltradeSvc
) -> dict[str, object]:
    await weltrade.ensure_user_session_bound(
        user_id=user.id, role=str(getattr(user, "role", "") or "")
    )
    return await _session_uc().execute(user_id=user.id)


@router.post("/robot/start")
async def start_robot(request: Request, user: CurrentUser) -> dict[str, object]:
    ip, ua = get_client_meta(request)
    return await _control_uc().execute(
        user_id=user.id,
        role=str(user.role or ""),
        display_name=user.display_name or user.email or str(user.id),
        action="start",
        ip=ip,
        user_agent=ua,
    )


@router.post("/robot/pause")
async def pause_robot(request: Request, user: CurrentUser) -> dict[str, object]:
    ip, ua = get_client_meta(request)
    return await _control_uc().execute(
        user_id=user.id,
        role=str(user.role or ""),
        display_name=user.display_name or user.email or str(user.id),
        action="pause",
        ip=ip,
        user_agent=ua,
    )


@router.post("/robot/stop")
async def stop_robot(request: Request, user: CurrentUser) -> dict[str, object]:
    ip, ua = get_client_meta(request)
    return await _control_uc().execute(
        user_id=user.id,
        role=str(user.role or ""),
        display_name=user.display_name or user.email or str(user.id),
        action="stop",
        ip=ip,
        user_agent=ua,
    )
