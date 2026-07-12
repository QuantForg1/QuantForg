"""In-memory fakes for application-layer unit tests.

These fakes implement domain ports without SQL or Redis. They exist only
under ``tests/`` and must never be imported by production code.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self
from uuid import UUID

from app.domain.entities.audit_log import AuditLog
from app.domain.entities.broker import Broker
from app.domain.entities.license import License
from app.domain.entities.risk_profile import RiskProfile
from app.domain.entities.signal import Signal
from app.domain.entities.symbol import Symbol
from app.domain.entities.trading_account import TradingAccount
from app.domain.entities.trading_session import TradingSession
from app.domain.entities.user import User
from app.domain.value_objects.email import EmailAddress
from app.domain.value_objects.identity import AccountNumber, EntitySlug


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.items.get(user_id)

    async def get_by_email(self, email: EmailAddress) -> User | None:
        for user in self.items.values():
            if user.email == email:
                return user
        return None

    async def get_by_auth_user_id(self, auth_user_id: UUID) -> User | None:
        for user in self.items.values():
            if user.auth_user_id == auth_user_id:
                return user
        return None

    async def add(self, user: User) -> User:
        self.items[user.id] = user
        return user

    async def update(self, user: User) -> User:
        self.items[user.id] = user
        return user


class InMemoryLicenseRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, License] = {}

    async def get_by_id(self, license_id: UUID) -> License | None:
        return self.items.get(license_id)

    async def add(self, license: License) -> License:
        self.items[license.id] = license
        return license

    async def update(self, license: License) -> License:
        self.items[license.id] = license
        return license


class InMemoryBrokerRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Broker] = {}

    async def get_by_id(self, broker_id: UUID) -> Broker | None:
        return self.items.get(broker_id)

    async def get_by_slug(self, slug: EntitySlug) -> Broker | None:
        for broker in self.items.values():
            if broker.slug == slug:
                return broker
        return None

    async def add(self, broker: Broker) -> Broker:
        self.items[broker.id] = broker
        return broker


class InMemoryTradingAccountRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, TradingAccount] = {}

    async def get_by_id(self, account_id: UUID) -> TradingAccount | None:
        return self.items.get(account_id)

    async def get_by_broker_and_number(
        self,
        broker_id: UUID,
        account_number: AccountNumber,
    ) -> TradingAccount | None:
        for account in self.items.values():
            if (
                account.broker_id == broker_id
                and account.account_number == account_number
            ):
                return account
        return None

    async def add(self, account: TradingAccount) -> TradingAccount:
        self.items[account.id] = account
        return account

    async def update(self, account: TradingAccount) -> TradingAccount:
        self.items[account.id] = account
        return account


class InMemoryTradingSessionRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, TradingSession] = {}

    async def get_by_id(self, session_id: UUID) -> TradingSession | None:
        return self.items.get(session_id)

    async def add(self, session: TradingSession) -> TradingSession:
        self.items[session.id] = session
        return session

    async def update(self, session: TradingSession) -> TradingSession:
        self.items[session.id] = session
        return session


class InMemorySymbolRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Symbol] = {}

    async def get_by_id(self, symbol_id: UUID) -> Symbol | None:
        return self.items.get(symbol_id)

    async def add(self, symbol: Symbol) -> Symbol:
        self.items[symbol.id] = symbol
        return symbol


class InMemorySignalRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Signal] = {}

    async def add(self, signal: Signal) -> Signal:
        self.items[signal.id] = signal
        return signal


class InMemoryRiskProfileRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, RiskProfile] = {}

    async def get_by_id(self, profile_id: UUID) -> RiskProfile | None:
        return self.items.get(profile_id)

    async def get_active_for_user(self, user_id: UUID) -> RiskProfile | None:
        for profile in self.items.values():
            if profile.user_id == user_id and profile.is_active:
                return profile
        return None

    async def get_active_for_account(
        self,
        trading_account_id: UUID,
    ) -> RiskProfile | None:
        for profile in self.items.values():
            if profile.trading_account_id == trading_account_id and profile.is_active:
                return profile
        return None

    async def add(self, profile: RiskProfile) -> RiskProfile:
        self.items[profile.id] = profile
        return profile


class InMemoryAuditLogRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, AuditLog] = {}

    async def add(self, entry: AuditLog) -> AuditLog:
        self.items[entry.id] = entry
        return entry


class InMemoryUnitOfWork:
    """Async context-manager UoW backed by in-memory repositories."""

    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.licenses = InMemoryLicenseRepository()
        self.brokers = InMemoryBrokerRepository()
        self.trading_accounts = InMemoryTradingAccountRepository()
        self.trading_sessions = InMemoryTradingSessionRepository()
        self.symbols = InMemorySymbolRepository()
        self.signals = InMemorySignalRepository()
        self.risk_profiles = InMemoryRiskProfileRepository()
        self.audit_logs = InMemoryAuditLogRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None and not self.committed:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class SharedUnitOfWorkFactory:
    """Returns the same in-memory UoW instance for every call.

    Enables tests to seed data and then execute use cases against it.
    """

    def __init__(self, uow: InMemoryUnitOfWork | None = None) -> None:
        self.uow = uow or InMemoryUnitOfWork()

    def __call__(self) -> InMemoryUnitOfWork:
        self.uow.committed = False
        self.uow.rolled_back = False
        return self.uow


class FakeAppInfo:
    """Minimal AppInfoPort double."""

    def __init__(
        self,
        *,
        app_name: str = "QuantForg",
        app_version: str = "0.1.0",
        environment: str = "testing",
        api_prefix: str = "/api/v1",
        health_check_timeout_seconds: float = 1.0,
    ) -> None:
        self._app_name = app_name
        self._app_version = app_version
        self._environment = environment
        self._api_prefix = api_prefix
        self._health_check_timeout_seconds = health_check_timeout_seconds

    @property
    def app_name(self) -> str:
        return self._app_name

    @property
    def app_version(self) -> str:
        return self._app_version

    @property
    def environment(self) -> str:
        return self._environment

    @property
    def api_prefix(self) -> str:
        return self._api_prefix

    @property
    def health_check_timeout_seconds(self) -> float:
        return self._health_check_timeout_seconds
