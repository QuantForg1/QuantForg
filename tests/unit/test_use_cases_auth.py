"""Unit tests for authentication use cases."""

from __future__ import annotations

import pytest

from app.application.dto.auth import (
    ChangePasswordCommand,
    LoginCommand,
    LogoutCommand,
    MessageDTO,
    OAuthCallbackCommand,
    OAuthStartCommand,
    RefreshSessionCommand,
    RegisterEmailCommand,
    RequestPasswordResetCommand,
    VerifyEmailCommand,
)
from app.application.use_cases.auth import (
    ChangePasswordUseCase,
    CompleteOAuthUseCase,
    GetCurrentUserUseCase,
    LoginUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
    RegisterWithEmailUseCase,
    RequestPasswordResetUseCase,
    StartOAuthUseCase,
    VerifyEmailUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.user import UserRole, UserStatus
from app.domain.exceptions.auth import AuthenticationError, AuthorizationError
from app.domain.exceptions.base import ValidationError
from app.domain.interfaces.auth import OAuthProvider
from app.domain.value_objects.email import EmailAddress
from tests.unit.fakes import SharedUnitOfWorkFactory
from tests.unit.fakes_auth import FakeAuthProvider


def _wire(auth: FakeAuthProvider | None = None, *, confirm: bool = False):
    factory = SharedUnitOfWorkFactory()
    provider = auth or FakeAuthProvider(require_email_confirm=confirm)
    audit = RecordAuditEventUseCase(uow_factory=factory)
    return factory, provider, audit


@pytest.mark.unit
class TestRegisterAndLogin:
    @pytest.mark.asyncio
    async def test_register_and_login_flow(self) -> None:
        factory, provider, audit = _wire()
        register = RegisterWithEmailUseCase(
            auth=provider, uow_factory=factory, audit=audit
        )
        session = await register.execute(
            RegisterEmailCommand(
                email="trader@quantforg.com",
                password="securepass1",
                display_name="Trader",
            )
        )
        assert not isinstance(session, MessageDTO)
        assert session.user.status == UserStatus.ACTIVE.value
        assert session.user.auth_user_id is not None

        login = LoginUseCase(auth=provider, uow_factory=factory, audit=audit)
        again = await login.execute(
            LoginCommand(email="trader@quantforg.com", password="securepass1")
        )
        assert again.access_token
        assert again.user.email == "trader@quantforg.com"
        assert len(factory.uow.audit_logs.items) >= 2

    @pytest.mark.asyncio
    async def test_register_requires_verification_message(self) -> None:
        factory, provider, audit = _wire(confirm=True)
        result = await RegisterWithEmailUseCase(
            auth=provider, uow_factory=factory, audit=audit
        ).execute(
            RegisterEmailCommand(
                email="pending@quantforg.com",
                password="securepass1",
                display_name="Pending",
            )
        )
        assert isinstance(result, MessageDTO)
        user = await factory.uow.users.get_by_email(
            EmailAddress(value="pending@quantforg.com")
        )
        assert user is not None
        assert user.status == UserStatus.PENDING

    @pytest.mark.asyncio
    async def test_weak_password_rejected(self) -> None:
        factory, provider, audit = _wire()
        with pytest.raises(ValidationError):
            await RegisterWithEmailUseCase(
                auth=provider, uow_factory=factory, audit=audit
            ).execute(
                RegisterEmailCommand(
                    email="a@b.com", password="short", display_name="A"
                )
            )


@pytest.mark.unit
class TestVerifyRefreshLogoutPassword:
    @pytest.mark.asyncio
    async def test_verify_email_activates(self) -> None:
        factory, provider, audit = _wire(confirm=True)
        await RegisterWithEmailUseCase(
            auth=provider, uow_factory=factory, audit=audit
        ).execute(
            RegisterEmailCommand(
                email="v@quantforg.com", password="securepass1", display_name="V"
            )
        )
        session = await VerifyEmailUseCase(
            auth=provider, uow_factory=factory, audit=audit
        ).execute(VerifyEmailCommand(token_hash="verify:v@quantforg.com"))
        assert session.user.status == UserStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_refresh_and_logout(self) -> None:
        factory, provider, audit = _wire()
        registered = await RegisterWithEmailUseCase(
            auth=provider, uow_factory=factory, audit=audit
        ).execute(
            RegisterEmailCommand(
                email="r@quantforg.com", password="securepass1", display_name="R"
            )
        )
        assert not isinstance(registered, MessageDTO)
        refreshed = await RefreshSessionUseCase(
            auth=provider, uow_factory=factory
        ).execute(RefreshSessionCommand(refresh_token=registered.refresh_token))
        assert refreshed.access_token
        msg = await LogoutUseCase(auth=provider, audit=audit).execute(
            LogoutCommand(
                access_token=refreshed.access_token,
                actor_user_id=refreshed.user.id,
            )
        )
        assert msg.message == "Logged out"

    @pytest.mark.asyncio
    async def test_change_password(self) -> None:
        factory, provider, audit = _wire()
        registered = await RegisterWithEmailUseCase(
            auth=provider, uow_factory=factory, audit=audit
        ).execute(
            RegisterEmailCommand(
                email="p@quantforg.com", password="securepass1", display_name="P"
            )
        )
        assert not isinstance(registered, MessageDTO)
        await ChangePasswordUseCase(auth=provider, audit=audit).execute(
            ChangePasswordCommand(
                access_token=registered.access_token,
                new_password="newsecure9",
                actor_user_id=registered.user.id,
            )
        )
        await LoginUseCase(auth=provider, uow_factory=factory, audit=audit).execute(
            LoginCommand(email="p@quantforg.com", password="newsecure9")
        )

    @pytest.mark.asyncio
    async def test_forgot_password_message(self) -> None:
        factory, provider, audit = _wire()
        msg = await RequestPasswordResetUseCase(
            auth=provider, audit=audit, default_redirect_to="http://localhost/reset"
        ).execute(RequestPasswordResetCommand(email="missing@quantforg.com"))
        assert "reset" in msg.message.lower()


@pytest.mark.unit
class TestOAuthAndRBAC:
    @pytest.mark.asyncio
    async def test_oauth_google_flow(self) -> None:
        factory, provider, audit = _wire()
        url = await StartOAuthUseCase(
            auth=provider, default_redirect_to="http://localhost/cb"
        ).execute(OAuthStartCommand(provider=OAuthProvider.GOOGLE))
        assert "google" in url.url
        session = await CompleteOAuthUseCase(
            auth=provider,
            uow_factory=factory,
            audit=audit,
            default_redirect_to="http://localhost/cb",
        ).execute(OAuthCallbackCommand(code="oauth:google:oauth.user@quantforg.com"))
        assert session.user.role == UserRole.TRADER.value
        assert session.user.status == UserStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_get_current_user_and_suspend_blocks_login(self) -> None:
        factory, provider, audit = _wire()
        registered = await RegisterWithEmailUseCase(
            auth=provider, uow_factory=factory, audit=audit
        ).execute(
            RegisterEmailCommand(
                email="s@quantforg.com", password="securepass1", display_name="S"
            )
        )
        assert not isinstance(registered, MessageDTO)
        me = await GetCurrentUserUseCase(auth=provider, uow_factory=factory).execute(
            access_token=registered.access_token
        )
        assert me.id == registered.user.id

        user = await factory.uow.users.get_by_id(registered.user.id)
        assert user is not None
        user.suspend()
        await factory.uow.users.update(user)

        with pytest.raises(AuthorizationError):
            await LoginUseCase(auth=provider, uow_factory=factory, audit=audit).execute(
                LoginCommand(email="s@quantforg.com", password="securepass1")
            )

    @pytest.mark.asyncio
    async def test_invalid_login_audited(self) -> None:
        factory, provider, audit = _wire()
        await RegisterWithEmailUseCase(
            auth=provider, uow_factory=factory, audit=audit
        ).execute(
            RegisterEmailCommand(
                email="bad@quantforg.com", password="securepass1", display_name="B"
            )
        )
        with pytest.raises(AuthenticationError):
            await LoginUseCase(auth=provider, uow_factory=factory, audit=audit).execute(
                LoginCommand(email="bad@quantforg.com", password="wrong-password")
            )
