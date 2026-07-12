"""Application facade for User Platform endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.platform import (
    EnsurePlatformBootstrapCommand,
    ProfileDTO,
)
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


@dataclass(frozen=True, slots=True)
class PlatformService:
    bootstrap: EnsurePlatformBootstrapUseCase
    get_profile: GetProfileUseCase
    update_profile: UpdateProfileUseCase
    get_settings: GetSettingsUseCase
    update_settings: UpdateSettingsUseCase
    list_devices: ListDevicesUseCase
    list_sessions: ListSessionsUseCase
    revoke_session: RevokeSessionUseCase
    list_organizations: ListOrganizationsUseCase
    create_team: CreateTeamOrganizationUseCase
    invite_member: InviteOrganizationMemberUseCase
    list_activity: ListActivityUseCase
    list_notifications: ListNotificationsUseCase
    mark_notification_read: MarkNotificationReadUseCase
    list_notification_preferences: ListNotificationPreferencesUseCase
    update_notification_preference: UpdateNotificationPreferenceUseCase
    set_avatar: SetAvatarUseCase

    async def ensure_bootstrap(
        self, user_id: UUID, display_name: str = ""
    ) -> ProfileDTO:
        return await self.bootstrap.execute(
            EnsurePlatformBootstrapCommand(user_id=user_id, display_name=display_name)
        )
