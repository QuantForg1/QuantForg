"""User settings REST API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.application.dto.platform import UpdateSettingsCommand
from app.domain.enums.platform import UiTheme
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.platform import PlatformSvc
from app.presentation.schemas.platform import (
    DeviceResponse,
    SessionResponse,
    SettingsResponse,
    UpdateSettingsRequest,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(user: CurrentUser, platform: PlatformSvc) -> SettingsResponse:
    dto = await platform.get_settings.execute(user_id=user.id)
    return SettingsResponse(**dto.__dict__)


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    body: UpdateSettingsRequest,
    request: Request,
    user: CurrentUser,
    platform: PlatformSvc,
) -> SettingsResponse:
    ip, ua = get_client_meta(request)
    dto = await platform.update_settings.execute(
        UpdateSettingsCommand(
            user_id=user.id,
            theme=UiTheme(body.theme) if body.theme else None,
            notifications_enabled=body.notifications_enabled,
            email_marketing=body.email_marketing,
            email_security=body.email_security,
            email_product=body.email_product,
            security_login_alerts=body.security_login_alerts,
            security_require_reauth=body.security_require_reauth,
            session_timeout_minutes=body.session_timeout_minutes,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return SettingsResponse(**dto.__dict__)


@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices(
    user: CurrentUser, platform: PlatformSvc
) -> list[DeviceResponse]:
    items = await platform.list_devices.execute(user_id=user.id)
    return [DeviceResponse(**i.__dict__) for i in items]


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user: CurrentUser, platform: PlatformSvc
) -> list[SessionResponse]:
    items = await platform.list_sessions.execute(user_id=user.id)
    return [SessionResponse(**i.__dict__) for i in items]


@router.post("/sessions/{session_id}/revoke", response_model=SessionResponse)
async def revoke_session(
    session_id: UUID, user: CurrentUser, platform: PlatformSvc
) -> SessionResponse:
    dto = await platform.revoke_session.execute(user_id=user.id, session_id=session_id)
    return SessionResponse(**dto.__dict__)
