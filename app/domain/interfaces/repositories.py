"""Aggregate-specific repository ports.

These protocols are the only persistence contracts the application layer
may depend on. Infrastructure adapters implement them later — this sprint
defines the contracts only.
"""

from __future__ import annotations

from typing import Protocol
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


class UserRepositoryPort(Protocol):
    """Persistence port for the User aggregate."""

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: EmailAddress) -> User | None: ...

    async def add(self, user: User) -> User: ...

    async def update(self, user: User) -> User: ...


class LicenseRepositoryPort(Protocol):
    """Persistence port for the License aggregate."""

    async def get_by_id(self, license_id: UUID) -> License | None: ...

    async def add(self, license: License) -> License: ...

    async def update(self, license: License) -> License: ...


class BrokerRepositoryPort(Protocol):
    """Persistence port for the Broker aggregate."""

    async def get_by_id(self, broker_id: UUID) -> Broker | None: ...

    async def get_by_slug(self, slug: EntitySlug) -> Broker | None: ...

    async def add(self, broker: Broker) -> Broker: ...


class TradingAccountRepositoryPort(Protocol):
    """Persistence port for the TradingAccount aggregate."""

    async def get_by_id(self, account_id: UUID) -> TradingAccount | None: ...

    async def get_by_broker_and_number(
        self,
        broker_id: UUID,
        account_number: AccountNumber,
    ) -> TradingAccount | None: ...

    async def add(self, account: TradingAccount) -> TradingAccount: ...

    async def update(self, account: TradingAccount) -> TradingAccount: ...


class TradingSessionRepositoryPort(Protocol):
    """Persistence port for the TradingSession aggregate."""

    async def get_by_id(self, session_id: UUID) -> TradingSession | None: ...

    async def add(self, session: TradingSession) -> TradingSession: ...

    async def update(self, session: TradingSession) -> TradingSession: ...


class SymbolRepositoryPort(Protocol):
    """Persistence port for the Symbol aggregate."""

    async def get_by_id(self, symbol_id: UUID) -> Symbol | None: ...


class SignalRepositoryPort(Protocol):
    """Persistence port for the Signal aggregate."""

    async def add(self, signal: Signal) -> Signal: ...


class RiskProfileRepositoryPort(Protocol):
    """Persistence port for the RiskProfile aggregate."""

    async def get_by_id(self, profile_id: UUID) -> RiskProfile | None: ...

    async def get_active_for_user(self, user_id: UUID) -> RiskProfile | None: ...

    async def get_active_for_account(
        self,
        trading_account_id: UUID,
    ) -> RiskProfile | None: ...


class AuditLogRepositoryPort(Protocol):
    """Persistence port for the AuditLog aggregate."""

    async def add(self, entry: AuditLog) -> AuditLog: ...
