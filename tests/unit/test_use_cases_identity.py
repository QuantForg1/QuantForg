"""Unit tests for identity and catalogue use cases."""

from __future__ import annotations

import pytest

from app.application.dto.broker import CreateBrokerCommand
from app.application.dto.license import ActivateLicenseCommand
from app.application.dto.user import RegisterUserCommand
from app.application.use_cases.activate_license import ActivateLicenseUseCase
from app.application.use_cases.create_broker import CreateBrokerUseCase
from app.application.use_cases.register_user import RegisterUserUseCase
from app.domain.entities.license import License
from app.domain.enums.license import LicenseStatus, LicenseTier
from app.domain.enums.user import UserStatus
from app.domain.exceptions.base import ConflictError, NotFoundError
from tests.unit.fakes import SharedUnitOfWorkFactory


@pytest.mark.unit
class TestRegisterUserUseCase:
    @pytest.mark.asyncio
    async def test_registers_pending_user(self) -> None:
        factory = SharedUnitOfWorkFactory()
        use_case = RegisterUserUseCase(uow_factory=factory)

        result = await use_case.execute(
            RegisterUserCommand(email="trader@quantforg.com", display_name="Trader")
        )

        assert result.email == "trader@quantforg.com"
        assert result.status == UserStatus.PENDING.value
        assert factory.uow.committed is True
        assert await factory.uow.users.get_by_id(result.id) is not None

    @pytest.mark.asyncio
    async def test_rejects_duplicate_email(self) -> None:
        factory = SharedUnitOfWorkFactory()
        use_case = RegisterUserUseCase(uow_factory=factory)
        await use_case.execute(
            RegisterUserCommand(email="dup@quantforg.com", display_name="One")
        )

        with pytest.raises(ConflictError):
            await use_case.execute(
                RegisterUserCommand(email="dup@quantforg.com", display_name="Two")
            )


@pytest.mark.unit
class TestActivateLicenseUseCase:
    @pytest.mark.asyncio
    async def test_activates_pending_license(self) -> None:
        factory = SharedUnitOfWorkFactory()
        user_id = (
            await RegisterUserUseCase(uow_factory=factory).execute(
                RegisterUserCommand(email="a@b.com", display_name="A")
            )
        ).id
        # Activate user so domain state is realistic for later flows.
        user = await factory.uow.users.get_by_id(user_id)
        assert user is not None
        user.activate()
        await factory.uow.users.update(user)

        license_ = License.create_pending(
            user_id=user_id,
            tier=LicenseTier.STARTER,
        )
        await factory.uow.licenses.add(license_)

        result = await ActivateLicenseUseCase(uow_factory=factory).execute(
            ActivateLicenseCommand(license_id=license_.id)
        )

        assert result.status == LicenseStatus.ACTIVE.value
        assert result.issued_at is not None

    @pytest.mark.asyncio
    async def test_missing_license(self) -> None:
        factory = SharedUnitOfWorkFactory()
        from uuid import uuid4

        with pytest.raises(NotFoundError):
            await ActivateLicenseUseCase(uow_factory=factory).execute(
                ActivateLicenseCommand(license_id=uuid4())
            )


@pytest.mark.unit
class TestCreateBrokerUseCase:
    @pytest.mark.asyncio
    async def test_creates_and_activates_broker(self) -> None:
        factory = SharedUnitOfWorkFactory()
        result = await CreateBrokerUseCase(uow_factory=factory).execute(
            CreateBrokerCommand(name="Acme", slug="acme", country_code="us")
        )
        assert result.slug == "acme"
        assert result.status == "active"
        assert result.country_code == "US"

    @pytest.mark.asyncio
    async def test_rejects_duplicate_slug(self) -> None:
        factory = SharedUnitOfWorkFactory()
        use_case = CreateBrokerUseCase(uow_factory=factory)
        await use_case.execute(CreateBrokerCommand(name="A", slug="same"))
        with pytest.raises(ConflictError):
            await use_case.execute(CreateBrokerCommand(name="B", slug="same"))
