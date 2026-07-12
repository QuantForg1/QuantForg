"""Unit tests for core domain entities (User, License, Broker, Account, Session)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.broker import Broker
from app.domain.entities.license import License
from app.domain.entities.trading_account import TradingAccount
from app.domain.entities.trading_session import TradingSession
from app.domain.entities.user import User
from app.domain.enums.broker import BrokerStatus
from app.domain.enums.license import LicenseStatus, LicenseTier
from app.domain.enums.trading_account import AccountStatus
from app.domain.enums.trading_session import SessionStatus
from app.domain.enums.user import UserRole, UserStatus
from app.domain.exceptions.base import ConflictError, ValidationError
from app.domain.value_objects.money import Money


@pytest.mark.unit
class TestUser:
    def test_create_and_activate(self) -> None:
        user = User.create(email="trader@quantforg.com", display_name="Trader One")
        assert user.status == UserStatus.PENDING
        user.activate()
        assert user.is_active
        user.record_login()
        assert user.last_login_at is not None

    def test_suspend_and_deactivate(self) -> None:
        user = User.create(email="a@b.com", display_name="A")
        user.activate()
        user.suspend()
        assert user.status == UserStatus.SUSPENDED
        user.activate()
        user.deactivate()
        assert user.status == UserStatus.DEACTIVATED
        with pytest.raises(ConflictError):
            user.change_role(UserRole.ADMIN)

    def test_login_requires_active(self) -> None:
        user = User.create(email="a@b.com", display_name="A")
        with pytest.raises(ConflictError):
            user.record_login()

    def test_link_auth_identity(self) -> None:
        user = User.create(email="a@b.com", display_name="A")
        auth_id = uuid4()
        user.link_auth_identity(auth_id)
        assert user.auth_user_id == auth_id
        user.link_auth_identity(auth_id)
        with pytest.raises(ConflictError):
            user.link_auth_identity(uuid4())

    def test_has_role(self) -> None:
        user = User.create(email="a@b.com", display_name="A", role=UserRole.ADMIN)
        assert user.has_role(UserRole.ADMIN, UserRole.OWNER)
        assert not user.has_role(UserRole.TRADER)


@pytest.mark.unit
class TestLicense:
    def test_issue_and_revoke(self) -> None:
        user_id = uuid4()
        license_ = License.issue(
            user_id=user_id,
            tier=LicenseTier.PROFESSIONAL,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        assert license_.status == LicenseStatus.ACTIVE
        assert license_.is_valid_at()
        license_.revoke(reason="chargeback")
        assert license_.status == LicenseStatus.REVOKED
        assert not license_.is_valid_at()

    def test_invalid_expiry(self) -> None:
        with pytest.raises(ValidationError):
            License.issue(
                user_id=uuid4(),
                tier=LicenseTier.TRIAL,
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )


@pytest.mark.unit
class TestBroker:
    def test_register_activate_block(self) -> None:
        broker = Broker.register(
            name="Acme Broker", slug="acme-broker", country_code="us"
        )
        assert broker.country_code == "US"
        broker.activate()
        assert broker.is_usable
        broker.deactivate()
        assert broker.status == BrokerStatus.INACTIVE
        broker.activate()
        broker.block()
        assert broker.status == BrokerStatus.BLOCKED


@pytest.mark.unit
class TestTradingAccount:
    def test_open_activate_balance(self) -> None:
        account = TradingAccount.open(
            user_id=uuid4(),
            broker_id=uuid4(),
            account_number="100200300",
            currency="USD",
            leverage=50,
        )
        assert account.status == AccountStatus.PENDING
        account.activate()
        assert account.is_tradable
        account.record_balance(Money.of("1000", "USD"))
        assert account.balance.amount == Money.of("1000", "USD").amount
        with pytest.raises(ValidationError):
            account.record_balance(Money.of("10", "EUR"))

    def test_close(self) -> None:
        account = TradingAccount.open(
            user_id=uuid4(),
            broker_id=uuid4(),
            account_number="ACC-9",
        )
        account.activate()
        account.close()
        assert account.status == AccountStatus.CLOSED
        with pytest.raises(ConflictError):
            account.change_leverage(200)


@pytest.mark.unit
class TestTradingSession:
    def test_lifecycle(self) -> None:
        session = TradingSession.open(
            trading_account_id=uuid4(),
            user_id=uuid4(),
            client_label="desktop",
        )
        assert session.is_open
        session.mark_idle()
        assert session.status == SessionStatus.IDLE
        session.heartbeat()
        assert session.status == SessionStatus.ACTIVE
        session.close(reason="logout")
        assert not session.is_open
        with pytest.raises(ConflictError):
            session.heartbeat()
