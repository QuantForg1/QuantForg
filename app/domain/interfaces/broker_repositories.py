"""Persistence ports for broker foundation aggregates."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.broker import Broker
from app.domain.entities.broker_integration import (
    BrokerAccount,
    BrokerCapability,
    BrokerConnection,
    BrokerCredential,
    BrokerSession,
)
from app.domain.enums.broker import BrokerCapabilityCode, BrokerCredentialType
from app.domain.value_objects.identity import EntitySlug


class BrokerCatalogueRepositoryPort(Protocol):
    """Persistence port for the Broker catalogue aggregate."""

    async def get_by_id(self, broker_id: UUID) -> Broker | None: ...

    async def get_by_slug(self, slug: EntitySlug) -> Broker | None: ...

    async def list_all(self) -> list[Broker]: ...

    async def add(self, broker: Broker) -> Broker: ...

    async def update(self, broker: Broker) -> Broker: ...

    async def delete(self, broker_id: UUID) -> None: ...


class BrokerCapabilityRepositoryPort(Protocol):
    async def list_for_broker(self, broker_id: UUID) -> list[BrokerCapability]: ...

    async def get_by_broker_and_code(
        self, broker_id: UUID, code: BrokerCapabilityCode
    ) -> BrokerCapability | None: ...

    async def add(self, capability: BrokerCapability) -> BrokerCapability: ...

    async def update(self, capability: BrokerCapability) -> BrokerCapability: ...

    async def delete(self, capability_id: UUID) -> None: ...


class BrokerAccountRepositoryPort(Protocol):
    async def get_by_id(self, account_id: UUID) -> BrokerAccount | None: ...

    async def list_all(self) -> list[BrokerAccount]: ...

    async def list_for_user(self, user_id: UUID) -> list[BrokerAccount]: ...

    async def get_by_user_broker_external(
        self,
        user_id: UUID,
        broker_id: UUID,
        external_account_id: str,
    ) -> BrokerAccount | None: ...

    async def add(self, account: BrokerAccount) -> BrokerAccount: ...

    async def update(self, account: BrokerAccount) -> BrokerAccount: ...

    async def delete(self, account_id: UUID) -> None: ...


class BrokerCredentialRepositoryPort(Protocol):
    async def get_by_id(self, credential_id: UUID) -> BrokerCredential | None: ...

    async def list_for_account(
        self, broker_account_id: UUID
    ) -> list[BrokerCredential]: ...

    async def get_by_account_and_type(
        self,
        broker_account_id: UUID,
        credential_type: BrokerCredentialType,
    ) -> BrokerCredential | None: ...

    async def add(self, credential: BrokerCredential) -> BrokerCredential: ...

    async def update(self, credential: BrokerCredential) -> BrokerCredential: ...

    async def delete(self, credential_id: UUID) -> None: ...

    async def delete_for_account(self, broker_account_id: UUID) -> None: ...


class BrokerConnectionRepositoryPort(Protocol):
    async def get_by_id(self, connection_id: UUID) -> BrokerConnection | None: ...

    async def get_for_account(
        self, broker_account_id: UUID
    ) -> BrokerConnection | None: ...

    async def list_for_user(self, user_id: UUID) -> list[BrokerConnection]: ...

    async def add(self, connection: BrokerConnection) -> BrokerConnection: ...

    async def update(self, connection: BrokerConnection) -> BrokerConnection: ...

    async def delete_for_account(self, broker_account_id: UUID) -> None: ...


class BrokerSessionRepositoryPort(Protocol):
    async def get_by_id(self, session_id: UUID) -> BrokerSession | None: ...

    async def get_active_for_account(
        self, broker_account_id: UUID
    ) -> BrokerSession | None: ...

    async def list_for_account(
        self, broker_account_id: UUID
    ) -> list[BrokerSession]: ...

    async def add(self, session: BrokerSession) -> BrokerSession: ...

    async def update(self, session: BrokerSession) -> BrokerSession: ...

    async def delete_for_account(self, broker_account_id: UUID) -> None: ...
