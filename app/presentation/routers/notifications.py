"""Notification Center REST API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.application.dto.platform import UpdateNotificationPreferenceCommand
from app.domain.enums.platform import NotificationCategory
from app.presentation.dependencies.auth import CurrentUser
from app.presentation.dependencies.platform import PlatformSvc
from app.presentation.dto_mapping import dto_to_dict
from app.presentation.schemas.platform import (
    NotificationPreferenceResponse,
    NotificationResponse,
    UpdateNotificationPreferenceRequest,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/preferences", response_model=list[NotificationPreferenceResponse])
async def list_preferences(
    user: CurrentUser, platform: PlatformSvc
) -> list[NotificationPreferenceResponse]:
    items = await platform.list_notification_preferences.execute(user_id=user.id)
    return [NotificationPreferenceResponse(**dto_to_dict(i)) for i in items]


@router.patch(
    "/preferences/{category}",
    response_model=NotificationPreferenceResponse,
)
async def update_preference(
    category: NotificationCategory,
    body: UpdateNotificationPreferenceRequest,
    user: CurrentUser,
    platform: PlatformSvc,
) -> NotificationPreferenceResponse:
    dto = await platform.update_notification_preference.execute(
        UpdateNotificationPreferenceCommand(
            user_id=user.id,
            category=category,
            in_app=body.in_app,
            email=body.email,
        )
    )
    return NotificationPreferenceResponse(**dto_to_dict(dto))


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    user: CurrentUser,
    platform: PlatformSvc,
    unread_only: bool = Query(default=False),
) -> list[NotificationResponse]:
    items = await platform.list_notifications.execute(
        user_id=user.id, unread_only=unread_only
    )
    return [NotificationResponse(**dto_to_dict(i)) for i in items]


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: UUID, user: CurrentUser, platform: PlatformSvc
) -> NotificationResponse:
    dto = await platform.mark_notification_read.execute(
        user_id=user.id, notification_id=notification_id
    )
    return NotificationResponse(**dto_to_dict(dto))
