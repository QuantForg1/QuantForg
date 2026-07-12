"""User Platform dependency wiring."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.application.services.platform_service import PlatformService
from app.application.use_cases.platform import (
    CreateTeamOrganizationUseCase,
    EnsurePlatformBootstrapUseCase,
    GetProfileUseCase,
    GetSettingsUseCase,
    InviteOrganizationMemberUseCase,
    ListActivityUseCase,
    ListDevicesUseCase,
    ListNotificationPreferencesUseCase,
    ListNotificationsUseCase,
    ListOrganizationsUseCase,
    ListSessionsUseCase,
    MarkNotificationReadUseCase,
    RevokeSessionUseCase,
    SetAvatarUseCase,
    UpdateNotificationPreferenceUseCase,
    UpdateProfileUseCase,
    UpdateSettingsUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.interfaces.platform_uow import PlatformUnitOfWorkFactory
from core.di.container import get_container


def get_platform_uow_factory() -> PlatformUnitOfWorkFactory:
    container = get_container()
    factory = getattr(container, "platform_uow_factory", None)
    if factory is None:
        msg = "Platform Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory  # type: ignore[no-any-return]


def get_platform_service() -> PlatformService:
    uow_factory = get_platform_uow_factory()
    audit = RecordAuditEventUseCase(uow_factory=uow_factory)  # type: ignore[arg-type]
    bootstrap = EnsurePlatformBootstrapUseCase(uow_factory=uow_factory)
    return PlatformService(
        bootstrap=bootstrap,
        get_profile=GetProfileUseCase(uow_factory=uow_factory, bootstrap=bootstrap),
        update_profile=UpdateProfileUseCase(uow_factory=uow_factory, audit=audit),
        get_settings=GetSettingsUseCase(uow_factory=uow_factory),
        update_settings=UpdateSettingsUseCase(uow_factory=uow_factory, audit=audit),
        list_devices=ListDevicesUseCase(uow_factory=uow_factory),
        list_sessions=ListSessionsUseCase(uow_factory=uow_factory),
        revoke_session=RevokeSessionUseCase(uow_factory=uow_factory),
        list_organizations=ListOrganizationsUseCase(uow_factory=uow_factory),
        create_team=CreateTeamOrganizationUseCase(uow_factory=uow_factory, audit=audit),
        invite_member=InviteOrganizationMemberUseCase(uow_factory=uow_factory),
        list_activity=ListActivityUseCase(uow_factory=uow_factory),
        list_notifications=ListNotificationsUseCase(uow_factory=uow_factory),
        mark_notification_read=MarkNotificationReadUseCase(uow_factory=uow_factory),
        list_notification_preferences=ListNotificationPreferencesUseCase(
            uow_factory=uow_factory
        ),
        update_notification_preference=UpdateNotificationPreferenceUseCase(
            uow_factory=uow_factory
        ),
        set_avatar=SetAvatarUseCase(uow_factory=uow_factory),
    )


PlatformSvc = Annotated[PlatformService, Depends(get_platform_service)]
