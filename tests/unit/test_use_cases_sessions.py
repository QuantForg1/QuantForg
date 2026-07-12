"""Unit tests for trading-account and session use cases."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.broker import CreateBrokerCommand
from app.application.dto.trading_account import ConnectTradingAccountCommand
from app.application.dto.trading_session import (
    CloseTradingSessionCommand,
    OpenTradingSessionCommand,
)
from app.application.dto.user import RegisterUserCommand
from app.application.use_cases.close_trading_session import CloseTradingSessionUseCase
from app.application.use_cases.connect_trading_account import (
    ConnectTradingAccountUseCase,
)
from app.application.use_cases.create_broker import CreateBrokerUseCase
from app.application.use_cases.open_trading_session import OpenTradingSessionUseCase
from app.application.use_cases.register_user import RegisterUserUseCase
from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError
from tests.unit.fakes import SharedUnitOfWorkFactory


async def _seed_active_user_and_broker(
    factory: SharedUnitOfWorkFactory,
) -> tuple:
    user_dto = await RegisterUserUseCase(uow_factory=factory).execute(
        RegisterUserCommand(email="trader@qf.com", display_name="Trader")
    )
    user = await factory.uow.users.get_by_id(user_dto.id)
    assert user is not None
    user.activate()
    await factory.uow.users.update(user)

    broker_dto = await CreateBrokerUseCase(uow_factory=factory).execute(
        CreateBrokerCommand(name="Broker", slug="broker-one")
    )
    return user_dto, broker_dto


@pytest.mark.unit
class TestConnectTradingAccountUseCase:
    @pytest.mark.asyncio
    async def test_connects_account(self) -> None:
        factory = SharedUnitOfWorkFactory()
        user_dto, broker_dto = await _seed_active_user_and_broker(factory)

        result = await ConnectTradingAccountUseCase(uow_factory=factory).execute(
            ConnectTradingAccountCommand(
                user_id=user_dto.id,
                broker_id=broker_dto.id,
                account_number="123456",
                leverage=50,
            )
        )

        assert result.status == "active"
        assert result.account_number == "123456"
        assert result.leverage == 50

    @pytest.mark.asyncio
    async def test_rejects_inactive_user(self) -> None:
        factory = SharedUnitOfWorkFactory()
        user_dto = await RegisterUserUseCase(uow_factory=factory).execute(
            RegisterUserCommand(email="pending@qf.com", display_name="P")
        )
        broker_dto = await CreateBrokerUseCase(uow_factory=factory).execute(
            CreateBrokerCommand(name="B", slug="b")
        )

        with pytest.raises(ValidationError):
            await ConnectTradingAccountUseCase(uow_factory=factory).execute(
                ConnectTradingAccountCommand(
                    user_id=user_dto.id,
                    broker_id=broker_dto.id,
                    account_number="999",
                )
            )

    @pytest.mark.asyncio
    async def test_rejects_duplicate_account(self) -> None:
        factory = SharedUnitOfWorkFactory()
        user_dto, broker_dto = await _seed_active_user_and_broker(factory)
        use_case = ConnectTradingAccountUseCase(uow_factory=factory)
        cmd = ConnectTradingAccountCommand(
            user_id=user_dto.id,
            broker_id=broker_dto.id,
            account_number="DUP-1",
        )
        await use_case.execute(cmd)
        with pytest.raises(ConflictError):
            await use_case.execute(cmd)


@pytest.mark.unit
class TestTradingSessionUseCases:
    @pytest.mark.asyncio
    async def test_open_and_close_session(self) -> None:
        factory = SharedUnitOfWorkFactory()
        user_dto, broker_dto = await _seed_active_user_and_broker(factory)
        account = await ConnectTradingAccountUseCase(uow_factory=factory).execute(
            ConnectTradingAccountCommand(
                user_id=user_dto.id,
                broker_id=broker_dto.id,
                account_number="555",
            )
        )

        opened = await OpenTradingSessionUseCase(uow_factory=factory).execute(
            OpenTradingSessionCommand(
                trading_account_id=account.id,
                user_id=user_dto.id,
                client_label="web",
            )
        )
        assert opened.status == "active"
        assert opened.client_label == "web"

        closed = await CloseTradingSessionUseCase(uow_factory=factory).execute(
            CloseTradingSessionCommand(session_id=opened.id, reason="logout")
        )
        assert closed.status == "closed"
        assert closed.termination_reason == "logout"

    @pytest.mark.asyncio
    async def test_open_rejects_wrong_user(self) -> None:
        factory = SharedUnitOfWorkFactory()
        user_dto, broker_dto = await _seed_active_user_and_broker(factory)
        account = await ConnectTradingAccountUseCase(uow_factory=factory).execute(
            ConnectTradingAccountCommand(
                user_id=user_dto.id,
                broker_id=broker_dto.id,
                account_number="555",
            )
        )

        with pytest.raises(NotFoundError):
            await OpenTradingSessionUseCase(uow_factory=factory).execute(
                OpenTradingSessionCommand(
                    trading_account_id=account.id,
                    user_id=uuid4(),
                )
            )

    @pytest.mark.asyncio
    async def test_close_missing_session(self) -> None:
        factory = SharedUnitOfWorkFactory()
        with pytest.raises(NotFoundError):
            await CloseTradingSessionUseCase(uow_factory=factory).execute(
                CloseTradingSessionCommand(session_id=uuid4())
            )
