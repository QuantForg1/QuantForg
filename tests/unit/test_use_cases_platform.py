"""Unit tests for User Platform use cases."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.platform import (
    CreateTeamCommand,
    EnsurePlatformBootstrapCommand,
    InviteMemberCommand,
    UpdateNotificationPreferenceCommand,
    UpdateProfileCommand,
    UpdateSettingsCommand,
)
from app.application.use_cases.platform import (
    CreateTeamOrganizationUseCase,
    EnsurePlatformBootstrapUseCase,
    GetProfileUseCase,
    GetSettingsUseCase,
    InviteOrganizationMemberUseCase,
    ListActivityUseCase,
    ListNotificationsUseCase,
    ListOrganizationsUseCase,
    MarkNotificationReadUseCase,
    RevokeSessionUseCase,
    SetAvatarUseCase,
    UpdateNotificationPreferenceUseCase,
    UpdateProfileUseCase,
    UpdateSettingsUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.platform import Notification, OrganizationMember, UserSession
from app.domain.enums.platform import (
    NotificationCategory,
    OrganizationMemberRole,
    ProfileRiskLevel,
    TradingExperience,
    UiTheme,
)
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import ConflictError, NotFoundError
from tests.unit.fakes_platform import SharedPlatformUnitOfWorkFactory


def _wire() -> tuple[SharedPlatformUnitOfWorkFactory, RecordAuditEventUseCase]:
    factory = SharedPlatformUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=factory)  # type: ignore[arg-type]
    return factory, audit


@pytest.mark.unit
class TestProfileAndSettings:
    @pytest.mark.asyncio
    async def test_bootstrap_profile_and_personal_org(self) -> None:
        factory, _audit = _wire()
        user_id = uuid4()
        profile = await EnsurePlatformBootstrapUseCase(uow_factory=factory).execute(
            EnsurePlatformBootstrapCommand(user_id=user_id, display_name="Ada")
        )
        assert profile.full_name == "Ada"
        orgs = await ListOrganizationsUseCase(uow_factory=factory).execute(
            user_id=user_id
        )
        assert len(orgs) == 1
        assert orgs[0].org_type == "personal"

    @pytest.mark.asyncio
    async def test_update_profile_and_settings(self) -> None:
        factory, audit = _wire()
        user_id = uuid4()
        await EnsurePlatformBootstrapUseCase(uow_factory=factory).execute(
            EnsurePlatformBootstrapCommand(user_id=user_id, display_name="Ada")
        )
        updated = await UpdateProfileUseCase(uow_factory=factory, audit=audit).execute(
            UpdateProfileCommand(
                user_id=user_id,
                username="ada_lovelace",
                bio="Mathematician",
                country_code="gb",
                trading_experience=TradingExperience.ADVANCED,
                risk_level=ProfileRiskLevel.AGGRESSIVE,
            )
        )
        assert updated.username == "ada_lovelace"
        assert updated.country_code == "GB"

        settings = await UpdateSettingsUseCase(
            uow_factory=factory, audit=audit
        ).execute(
            UpdateSettingsCommand(
                user_id=user_id,
                theme=UiTheme.DARK,
                email_marketing=True,
                session_timeout_minutes=60,
            )
        )
        assert settings.theme == "dark"
        assert settings.session_timeout_minutes == 60

        activity = await ListActivityUseCase(uow_factory=factory).execute(
            user_id=user_id
        )
        assert any(a.action == "profile_updated" for a in activity)

    @pytest.mark.asyncio
    async def test_duplicate_username(self) -> None:
        factory, audit = _wire()
        a, b = uuid4(), uuid4()
        await EnsurePlatformBootstrapUseCase(uow_factory=factory).execute(
            EnsurePlatformBootstrapCommand(user_id=a, display_name="A")
        )
        await EnsurePlatformBootstrapUseCase(uow_factory=factory).execute(
            EnsurePlatformBootstrapCommand(user_id=b, display_name="B")
        )
        await UpdateProfileUseCase(uow_factory=factory, audit=audit).execute(
            UpdateProfileCommand(user_id=a, username="taken")
        )
        with pytest.raises(ConflictError):
            await UpdateProfileUseCase(uow_factory=factory, audit=audit).execute(
                UpdateProfileCommand(user_id=b, username="taken")
            )


@pytest.mark.unit
class TestOrganizationsNotificationsAvatar:
    @pytest.mark.asyncio
    async def test_create_team_and_invite(self) -> None:
        factory, audit = _wire()
        user_id = uuid4()
        await EnsurePlatformBootstrapUseCase(uow_factory=factory).execute(
            EnsurePlatformBootstrapCommand(user_id=user_id, display_name="Owner")
        )
        team = await CreateTeamOrganizationUseCase(
            uow_factory=factory, audit=audit
        ).execute(
            CreateTeamCommand(
                owner_user_id=user_id, name="Alpha Desk", slug="alpha-desk"
            )
        )
        invite = await InviteOrganizationMemberUseCase(uow_factory=factory).execute(
            InviteMemberCommand(
                organization_id=team.id,
                invited_by=user_id,
                email="trader@quantforg.com",
                role=OrganizationMemberRole.MEMBER,
            )
        )
        assert invite.status == "pending"
        stranger = uuid4()
        with pytest.raises(AuthorizationError):
            await InviteOrganizationMemberUseCase(uow_factory=factory).execute(
                InviteMemberCommand(
                    organization_id=team.id,
                    invited_by=stranger,
                    email="x@y.com",
                )
            )
        with pytest.raises(AuthorizationError, match="Owner role cannot"):
            await InviteOrganizationMemberUseCase(uow_factory=factory).execute(
                InviteMemberCommand(
                    organization_id=team.id,
                    invited_by=user_id,
                    email="boss@quantforg.com",
                    role=OrganizationMemberRole.OWNER,
                )
            )

    @pytest.mark.asyncio
    async def test_admin_cannot_invite_admin(self) -> None:
        factory, audit = _wire()
        owner_id = uuid4()
        admin_id = uuid4()
        await EnsurePlatformBootstrapUseCase(uow_factory=factory).execute(
            EnsurePlatformBootstrapCommand(user_id=owner_id, display_name="Owner")
        )
        await EnsurePlatformBootstrapUseCase(uow_factory=factory).execute(
            EnsurePlatformBootstrapCommand(user_id=admin_id, display_name="Admin")
        )
        team = await CreateTeamOrganizationUseCase(
            uow_factory=factory, audit=audit
        ).execute(
            CreateTeamCommand(
                owner_user_id=owner_id, name="Beta Desk", slug="beta-desk"
            )
        )
        async with factory() as uow:
            await uow.organization_members.add(
                OrganizationMember(
                    organization_id=team.id,
                    user_id=admin_id,
                    role=OrganizationMemberRole.ADMIN,
                )
            )
            await uow.commit()
        with pytest.raises(AuthorizationError, match="traders or viewers"):
            await InviteOrganizationMemberUseCase(uow_factory=factory).execute(
                InviteMemberCommand(
                    organization_id=team.id,
                    invited_by=admin_id,
                    email="peer@quantforg.com",
                    role=OrganizationMemberRole.ADMIN,
                )
            )
        ok = await InviteOrganizationMemberUseCase(uow_factory=factory).execute(
            InviteMemberCommand(
                organization_id=team.id,
                invited_by=admin_id,
                email="viewer@quantforg.com",
                role=OrganizationMemberRole.VIEWER,
            )
        )
        assert ok.status == "pending"

    @pytest.mark.asyncio
    async def test_notifications_and_preferences(self) -> None:
        factory, _audit = _wire()
        user_id = uuid4()
        await EnsurePlatformBootstrapUseCase(uow_factory=factory).execute(
            EnsurePlatformBootstrapCommand(user_id=user_id, display_name="N")
        )
        note = Notification(
            user_id=user_id,
            category=NotificationCategory.SYSTEM,
            title="Welcome",
            body="Hello",
        )
        await factory.uow.notifications.add(note)
        listed = await ListNotificationsUseCase(uow_factory=factory).execute(
            user_id=user_id
        )
        assert listed[0].is_read is False
        read = await MarkNotificationReadUseCase(uow_factory=factory).execute(
            user_id=user_id, notification_id=note.id
        )
        assert read.is_read is True
        pref = await UpdateNotificationPreferenceUseCase(uow_factory=factory).execute(
            UpdateNotificationPreferenceCommand(
                user_id=user_id,
                category=NotificationCategory.PRODUCT,
                email=False,
            )
        )
        assert pref.email is False

    @pytest.mark.asyncio
    async def test_avatar_and_session_revoke(self) -> None:
        factory, _audit = _wire()
        user_id = uuid4()
        await EnsurePlatformBootstrapUseCase(uow_factory=factory).execute(
            EnsurePlatformBootstrapCommand(user_id=user_id, display_name="A")
        )
        profile = await SetAvatarUseCase(uow_factory=factory).execute(
            user_id=user_id,
            object_path=f"{user_id}/a.png",
            public_url="https://cdn.example/a.png",
            content_type="image/png",
            size_bytes=1024,
        )
        assert profile.avatar_url.endswith("a.png")

        session = UserSession(user_id=user_id, ip_address="127.0.0.1")
        await factory.uow.sessions.add(session)
        revoked = await RevokeSessionUseCase(uow_factory=factory).execute(
            user_id=user_id, session_id=session.id
        )
        assert revoked.is_active is False
        with pytest.raises(NotFoundError):
            await RevokeSessionUseCase(uow_factory=factory).execute(
                user_id=user_id, session_id=uuid4()
            )

    @pytest.mark.asyncio
    async def test_get_profile_bootstraps(self) -> None:
        factory, _audit = _wire()
        user_id = uuid4()
        bootstrap = EnsurePlatformBootstrapUseCase(uow_factory=factory)
        dto = await GetProfileUseCase(uow_factory=factory, bootstrap=bootstrap).execute(
            user_id=user_id, display_name="Boot"
        )
        assert dto.user_id == user_id
        settings = await GetSettingsUseCase(uow_factory=factory).execute(
            user_id=user_id
        )
        assert settings.theme == "system"
