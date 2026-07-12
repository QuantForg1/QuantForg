"""Unit of Work port.

Coordinates transactional boundaries across aggregate repositories.
Infrastructure provides the concrete implementation; application use cases
depend only on this protocol.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.domain.interfaces.repositories import (
    AuditLogRepositoryPort,
    BrokerRepositoryPort,
    LicenseRepositoryPort,
    RiskProfileRepositoryPort,
    SignalRepositoryPort,
    SymbolRepositoryPort,
    TradingAccountRepositoryPort,
    TradingSessionRepositoryPort,
    UserRepositoryPort,
)


class UnitOfWorkPort(Protocol):
    """Async unit-of-work exposing typed repository ports.

    Usage
    -----
    async with uow_factory() as uow:
        user = await uow.users.get_by_id(...)
        await uow.users.add(user)
        await uow.commit()
    """

    users: UserRepositoryPort
    licenses: LicenseRepositoryPort
    brokers: BrokerRepositoryPort
    trading_accounts: TradingAccountRepositoryPort
    trading_sessions: TradingSessionRepositoryPort
    symbols: SymbolRepositoryPort
    signals: SignalRepositoryPort
    risk_profiles: RiskProfileRepositoryPort
    audit_logs: AuditLogRepositoryPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None:
        """Persist all pending changes atomically."""
        ...

    async def rollback(self) -> None:
        """Discard all pending changes."""
        ...


class UnitOfWorkFactory(Protocol):
    """Creates a fresh :class:`UnitOfWorkPort` per use-case execution."""

    def __call__(self) -> UnitOfWorkPort:
        """Return a UoW usable as an async context manager."""
        ...
