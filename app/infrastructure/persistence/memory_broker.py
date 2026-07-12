"""In-memory persistence for Broker Foundation (tests + local runtime)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from app.domain.entities.broker import Broker
from app.domain.entities.broker_integration import (
    BrokerAccount,
    BrokerCapability,
    BrokerConnection,
    BrokerCredential,
    BrokerSession,
)
from app.domain.enums.broker import (
    BrokerCapabilityCode,
    BrokerConnectionStatus,
    BrokerCredentialType,
)
from app.domain.value_objects.identity import EntitySlug
from app.infrastructure.persistence.memory_platform import InMemoryAuditLogRepository


class InMemoryBrokerCatalogueRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Broker] = {}

    async def get_by_id(self, broker_id: UUID) -> Broker | None:
        return self.items.get(broker_id)

    async def get_by_slug(self, slug: EntitySlug) -> Broker | None:
        for broker in self.items.values():
            if broker.slug == slug:
                return broker
        return None

    async def list_all(self) -> list[Broker]:
        return list(self.items.values())

    async def add(self, broker: Broker) -> Broker:
        self.items[broker.id] = broker
        return broker

    async def update(self, broker: Broker) -> Broker:
        self.items[broker.id] = broker
        return broker

    async def delete(self, broker_id: UUID) -> None:
        self.items.pop(broker_id, None)


class InMemoryBrokerCapabilityRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, BrokerCapability] = {}

    async def list_for_broker(self, broker_id: UUID) -> list[BrokerCapability]:
        return [c for c in self.items.values() if c.broker_id == broker_id]

    async def get_by_broker_and_code(
        self, broker_id: UUID, code: BrokerCapabilityCode
    ) -> BrokerCapability | None:
        for cap in self.items.values():
            if cap.broker_id == broker_id and cap.code == code:
                return cap
        return None

    async def add(self, capability: BrokerCapability) -> BrokerCapability:
        self.items[capability.id] = capability
        return capability

    async def update(self, capability: BrokerCapability) -> BrokerCapability:
        self.items[capability.id] = capability
        return capability

    async def delete(self, capability_id: UUID) -> None:
        self.items.pop(capability_id, None)


class InMemoryBrokerAccountRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, BrokerAccount] = {}

    async def get_by_id(self, account_id: UUID) -> BrokerAccount | None:
        return self.items.get(account_id)

    async def list_all(self) -> list[BrokerAccount]:
        return list(self.items.values())

    async def list_for_user(self, user_id: UUID) -> list[BrokerAccount]:
        return [a for a in self.items.values() if a.user_id == user_id]

    async def get_by_user_broker_external(
        self,
        user_id: UUID,
        broker_id: UUID,
        external_account_id: str,
    ) -> BrokerAccount | None:
        target = external_account_id.strip().lower()
        for account in self.items.values():
            if (
                account.user_id == user_id
                and account.broker_id == broker_id
                and account.external_account_id.lower() == target
            ):
                return account
        return None

    async def add(self, account: BrokerAccount) -> BrokerAccount:
        self.items[account.id] = account
        return account

    async def update(self, account: BrokerAccount) -> BrokerAccount:
        self.items[account.id] = account
        return account

    async def delete(self, account_id: UUID) -> None:
        self.items.pop(account_id, None)


class InMemoryBrokerCredentialRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, BrokerCredential] = {}

    async def get_by_id(self, credential_id: UUID) -> BrokerCredential | None:
        return self.items.get(credential_id)

    async def list_for_account(self, broker_account_id: UUID) -> list[BrokerCredential]:
        return [
            c for c in self.items.values() if c.broker_account_id == broker_account_id
        ]

    async def get_by_account_and_type(
        self,
        broker_account_id: UUID,
        credential_type: BrokerCredentialType,
    ) -> BrokerCredential | None:
        for cred in self.items.values():
            if (
                cred.broker_account_id == broker_account_id
                and cred.credential_type == credential_type
            ):
                return cred
        return None

    async def add(self, credential: BrokerCredential) -> BrokerCredential:
        self.items[credential.id] = credential
        return credential

    async def update(self, credential: BrokerCredential) -> BrokerCredential:
        self.items[credential.id] = credential
        return credential

    async def delete(self, credential_id: UUID) -> None:
        self.items.pop(credential_id, None)

    async def delete_for_account(self, broker_account_id: UUID) -> None:
        to_remove = [
            cid
            for cid, cred in self.items.items()
            if cred.broker_account_id == broker_account_id
        ]
        for cid in to_remove:
            del self.items[cid]


class InMemoryBrokerConnectionRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, BrokerConnection] = {}
        self._accounts: InMemoryBrokerAccountRepository | None = None

    def bind_accounts(self, accounts: InMemoryBrokerAccountRepository) -> None:
        self._accounts = accounts

    async def get_by_id(self, connection_id: UUID) -> BrokerConnection | None:
        return self.items.get(connection_id)

    async def get_for_account(self, broker_account_id: UUID) -> BrokerConnection | None:
        for conn in self.items.values():
            if conn.broker_account_id == broker_account_id:
                return conn
        return None

    async def list_for_user(self, user_id: UUID) -> list[BrokerConnection]:
        if self._accounts is None:
            return list(self.items.values())
        account_ids = {
            a.id for a in self._accounts.items.values() if a.user_id == user_id
        }
        return [c for c in self.items.values() if c.broker_account_id in account_ids]

    async def add(self, connection: BrokerConnection) -> BrokerConnection:
        self.items[connection.id] = connection
        return connection

    async def update(self, connection: BrokerConnection) -> BrokerConnection:
        self.items[connection.id] = connection
        return connection

    async def delete_for_account(self, broker_account_id: UUID) -> None:
        to_remove = [
            cid
            for cid, conn in self.items.items()
            if conn.broker_account_id == broker_account_id
        ]
        for cid in to_remove:
            del self.items[cid]


class InMemoryBrokerSessionRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, BrokerSession] = {}

    async def get_by_id(self, session_id: UUID) -> BrokerSession | None:
        return self.items.get(session_id)

    async def get_active_for_account(
        self, broker_account_id: UUID
    ) -> BrokerSession | None:
        for session in self.items.values():
            if (
                session.broker_account_id == broker_account_id
                and session.status == BrokerConnectionStatus.CONNECTED
            ):
                return session
        return None

    async def list_for_account(self, broker_account_id: UUID) -> list[BrokerSession]:
        return [
            s for s in self.items.values() if s.broker_account_id == broker_account_id
        ]

    async def add(self, session: BrokerSession) -> BrokerSession:
        self.items[session.id] = session
        return session

    async def update(self, session: BrokerSession) -> BrokerSession:
        self.items[session.id] = session
        return session

    async def delete_for_account(self, broker_account_id: UUID) -> None:
        to_remove = [
            sid
            for sid, session in self.items.items()
            if session.broker_account_id == broker_account_id
        ]
        for sid in to_remove:
            del self.items[sid]


class InMemoryBrokerUnitOfWork:
    def __init__(self) -> None:
        self.brokers = InMemoryBrokerCatalogueRepository()
        self.capabilities = InMemoryBrokerCapabilityRepository()
        self.accounts = InMemoryBrokerAccountRepository()
        self.credentials = InMemoryBrokerCredentialRepository()
        self.connections = InMemoryBrokerConnectionRepository()
        self.connections.bind_accounts(self.accounts)
        self.sessions = InMemoryBrokerSessionRepository()
        # Shared with RecordAuditEventUseCase (same pattern as platform UoW).
        self.audit_logs = InMemoryAuditLogRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type is not None and not self.committed:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class MemoryBrokerUnitOfWorkFactory:
    def __init__(self, uow: InMemoryBrokerUnitOfWork | None = None) -> None:
        self.uow = uow or InMemoryBrokerUnitOfWork()

    def __call__(self) -> InMemoryBrokerUnitOfWork:
        self.uow.committed = False
        self.uow.rolled_back = False
        return self.uow
