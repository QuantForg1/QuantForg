"""Authenticated trading session — status and owned-account robot control.

Does not duplicate ITE ops. Robot mutations require an owned live broker
connection. Traders may control their own account robot (CONTROL_OWN_ROBOT).
Owner/admin global kill-switch and mode remain on /ite/ops.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.application.services.trading_session import (
    ControlTradingRobotUseCase,
    GetTradingSessionUseCase,
)
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.mt5 import get_mt5_adapter, get_mt5_uow_factory

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
async def get_trading_session(user: CurrentUser) -> dict[str, object]:
    return await _session_uc().execute(user_id=user.id)


@router.get("/account")
async def get_trading_account(user: CurrentUser) -> dict[str, object]:
    return await _session_uc().execute(user_id=user.id)


@router.get("/robot/status")
async def get_robot_status(user: CurrentUser) -> dict[str, object]:
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
