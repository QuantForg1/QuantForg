"""Unit of Work port for broker foundation persistence."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.domain.interfaces.broker_repositories import (
    BrokerAccountRepositoryPort,
    BrokerCapabilityRepositoryPort,
    BrokerCatalogueRepositoryPort,
    BrokerConnectionRepositoryPort,
    BrokerCredentialRepositoryPort,
    BrokerSessionRepositoryPort,
)


class BrokerUnitOfWorkPort(Protocol):
    """Transactional boundary for broker foundation aggregates."""

    brokers: BrokerCatalogueRepositoryPort
    capabilities: BrokerCapabilityRepositoryPort
    accounts: BrokerAccountRepositoryPort
    credentials: BrokerCredentialRepositoryPort
    connections: BrokerConnectionRepositoryPort
    sessions: BrokerSessionRepositoryPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class BrokerUnitOfWorkFactory(Protocol):
    def __call__(self) -> BrokerUnitOfWorkPort: ...
