"""Broker Foundation use cases — catalogue and account CRUD only.

No live broker connections, MT5, or trading execution.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from uuid import UUID

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.broker import (
    BrokerAccountDTO,
    BrokerConnectionDTO,
    BrokerDTO,
    ConnectBrokerCommand,
    CreateBrokerAccountCommand,
    CreateBrokerCommand,
    DeleteBrokerAccountCommand,
    DeleteBrokerCommand,
    DisconnectBrokerCommand,
    UpdateBrokerAccountCommand,
    UpdateBrokerCommand,
    ValidateBrokerCommand,
    ValidateBrokerResultDTO,
)
from app.application.services.broker_health import (
    AutomaticReconnectManager,
    ConnectionHealthMonitor,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.broker import Broker
from app.domain.entities.broker_integration import (
    BrokerAccount,
    BrokerCapability,
    BrokerConnection,
    BrokerCredential,
    BrokerSession,
)
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.broker import (
    BrokerAccountStatus,
    BrokerCapabilityCode,
    BrokerCredentialType,
    BrokerStatus,
)
from app.domain.events.broker import (
    BrokerConnected,
    BrokerDeleted,
    BrokerDisconnected,
    BrokerRegistered,
    CredentialsUpdated,
)
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.domain.interfaces.broker_adapter import BrokerConnectRequest
from app.domain.interfaces.broker_capability_discovery import (
    default_capabilities_for_platform,
)
from app.domain.interfaces.broker_registry import BrokerRegistryPort
from app.domain.interfaces.broker_uow import BrokerUnitOfWorkFactory
from app.domain.value_objects.identity import EntitySlug
from core.security.credential_encryption import CredentialEncryptionService
from core.security.crypto import credential_hint, decrypt_secret


def _default_capabilities(
    platform_code: str,
) -> tuple[BrokerCapabilityCode, ...]:
    """Baseline capability set advertised for a platform."""
    return default_capabilities_for_platform(platform_code)


@dataclass(frozen=True, slots=True)
class ListBrokersUseCase:
    uow_factory: BrokerUnitOfWorkFactory

    async def execute(self) -> list[BrokerDTO]:
        async with self.uow_factory() as uow:
            brokers = await uow.brokers.list_all()
            result: list[BrokerDTO] = []
            for broker in brokers:
                caps = await uow.capabilities.list_for_broker(broker.id)
                result.append(BrokerDTO.from_entity(broker, capabilities=caps))
            return result


@dataclass(frozen=True, slots=True)
class GetBrokerUseCase:
    uow_factory: BrokerUnitOfWorkFactory

    async def execute(self, *, broker_id: UUID) -> BrokerDTO:
        async with self.uow_factory() as uow:
            broker = await uow.brokers.get_by_id(broker_id)
            if broker is None:
                raise NotFoundError(
                    "Broker not found",
                    details={"broker_id": str(broker_id)},
                )
            caps = await uow.capabilities.list_for_broker(broker.id)
            return BrokerDTO.from_entity(broker, capabilities=caps)


@dataclass(frozen=True, slots=True)
class CreateBrokerUseCase:
    uow_factory: BrokerUnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(self, command: CreateBrokerCommand) -> BrokerDTO:
        broker = Broker.register(
            name=command.name,
            slug=command.slug,
            broker_type=command.broker_type,
            platform_code=command.platform_code,
            country_code=command.country_code,
            website=command.website,
            description=command.description,
        )
        if command.activate:
            broker.activate()

        codes = command.capability_codes or _default_capabilities(
            command.platform_code.value
        )

        async with self.uow_factory() as uow:
            existing = await uow.brokers.get_by_slug(EntitySlug(value=command.slug))
            if existing is not None:
                raise ConflictError(
                    "Broker slug already exists",
                    details={"slug": command.slug},
                )
            await uow.brokers.add(broker)
            caps: list[BrokerCapability] = []
            for code in codes:
                cap = BrokerCapability.declare(broker_id=broker.id, code=code)
                await uow.capabilities.add(cap)
                caps.append(cap)
            await uow.commit()
            dto = BrokerDTO.from_entity(broker, capabilities=caps)

        event = BrokerRegistered(
            broker_id=broker.id,
            slug=str(broker.slug),
            platform_code=broker.platform_code.value,
        )
        _ = event  # available for event bus wiring in later sprints

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.CREATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="broker",
                resource_id=broker.id,
                actor_user_id=command.actor_user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="Broker catalogue entry created",
                metadata={"event_type": event.event_type},
            )
        )
        return dto


# Sprint 1 alias
RegisterBrokerUseCase = CreateBrokerUseCase


@dataclass(frozen=True, slots=True)
class UpdateBrokerUseCase:
    uow_factory: BrokerUnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(self, command: UpdateBrokerCommand) -> BrokerDTO:
        async with self.uow_factory() as uow:
            broker = await uow.brokers.get_by_id(command.broker_id)
            if broker is None:
                raise NotFoundError(
                    "Broker not found",
                    details={"broker_id": str(command.broker_id)},
                )
            broker.update_catalogue(
                name=command.name,
                broker_type=command.broker_type,
                platform_code=command.platform_code,
                country_code=command.country_code,
                website=command.website,
                description=command.description,
            )
            if command.status is not None and command.status != broker.status:
                self._apply_status(broker, command.status)
            await uow.brokers.update(broker)
            caps = await uow.capabilities.list_for_broker(broker.id)
            await uow.commit()
            dto = BrokerDTO.from_entity(broker, capabilities=caps)

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.UPDATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="broker",
                resource_id=broker.id,
                actor_user_id=command.actor_user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="Broker catalogue entry updated",
            )
        )
        return dto

    @staticmethod
    def _apply_status(broker: Broker, status: BrokerStatus) -> None:
        if status == BrokerStatus.ACTIVE:
            broker.activate()
        elif status == BrokerStatus.INACTIVE:
            broker.deactivate()
        elif status == BrokerStatus.BLOCKED:
            broker.block()
        elif status == BrokerStatus.PENDING:
            raise ValidationError(
                "Cannot revert broker status to pending",
                details={"status": status.value},
            )


@dataclass(frozen=True, slots=True)
class DeleteBrokerUseCase:
    uow_factory: BrokerUnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(self, command: DeleteBrokerCommand) -> None:
        async with self.uow_factory() as uow:
            broker = await uow.brokers.get_by_id(command.broker_id)
            if broker is None:
                raise NotFoundError(
                    "Broker not found",
                    details={"broker_id": str(command.broker_id)},
                )
            linked = [
                a
                for a in await uow.accounts.list_all()
                if a.broker_id == command.broker_id
                and a.status != BrokerAccountStatus.REVOKED
            ]
            if linked:
                raise ConflictError(
                    "Cannot delete broker with linked accounts",
                    details={"broker_id": str(command.broker_id)},
                )
            for cap in await uow.capabilities.list_for_broker(broker.id):
                await uow.capabilities.delete(cap.id)
            slug = str(broker.slug)
            await uow.brokers.delete(broker.id)
            await uow.commit()

        deleted = BrokerDeleted(broker_id=command.broker_id, slug=slug)
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.DELETE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="broker",
                resource_id=command.broker_id,
                actor_user_id=command.actor_user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="Broker catalogue entry deleted",
                metadata={"event_type": deleted.event_type, "slug": slug},
            )
        )


@dataclass(frozen=True, slots=True)
class ListBrokerAccountsUseCase:
    uow_factory: BrokerUnitOfWorkFactory

    async def execute(self, *, user_id: UUID) -> list[BrokerAccountDTO]:
        async with self.uow_factory() as uow:
            accounts = await uow.accounts.list_for_user(user_id)
            result: list[BrokerAccountDTO] = []
            for account in accounts:
                connection = await uow.connections.get_for_account(account.id)
                credentials = await uow.credentials.list_for_account(account.id)
                result.append(
                    BrokerAccountDTO.from_entity(
                        account,
                        connection=connection,
                        credentials=credentials,
                    )
                )
            return result


@dataclass(frozen=True, slots=True)
class GetBrokerAccountUseCase:
    uow_factory: BrokerUnitOfWorkFactory

    async def execute(self, *, user_id: UUID, account_id: UUID) -> BrokerAccountDTO:
        async with self.uow_factory() as uow:
            account = await uow.accounts.get_by_id(account_id)
            if account is None or account.user_id != user_id:
                raise NotFoundError(
                    "Broker account not found",
                    details={"account_id": str(account_id)},
                )
            connection = await uow.connections.get_for_account(account.id)
            credentials = await uow.credentials.list_for_account(account.id)
            return BrokerAccountDTO.from_entity(
                account,
                connection=connection,
                credentials=credentials,
            )


@dataclass(frozen=True, slots=True)
class CreateBrokerAccountUseCase:
    uow_factory: BrokerUnitOfWorkFactory
    audit: RecordAuditEventUseCase
    encryption_key: str
    encryption_key_version: int = 1
    previous_encryption_keys: tuple[str, ...] = ()

    async def execute(self, command: CreateBrokerAccountCommand) -> BrokerAccountDTO:
        async with self.uow_factory() as uow:
            broker = await uow.brokers.get_by_id(command.broker_id)
            if broker is None:
                raise NotFoundError(
                    "Broker not found",
                    details={"broker_id": str(command.broker_id)},
                )
            if not broker.is_usable:
                raise ValidationError(
                    "Broker is not available for new accounts",
                    details={"status": broker.status.value},
                )
            duplicate = await uow.accounts.get_by_user_broker_external(
                command.user_id,
                command.broker_id,
                command.external_account_id.strip(),
            )
            if (
                duplicate is not None
                and duplicate.status != BrokerAccountStatus.REVOKED
            ):
                raise ConflictError(
                    "Broker account already linked",
                    details={"external_account_id": command.external_account_id},
                )

            account = BrokerAccount.link(
                user_id=command.user_id,
                broker_id=command.broker_id,
                external_account_id=command.external_account_id,
                label=command.label,
                environment=command.environment,
                server=command.server,
                metadata=command.metadata,
            )
            await uow.accounts.add(account)
            connection = BrokerConnection.create_for_account(
                broker_account_id=account.id
            )
            await uow.connections.add(connection)
            credentials = await _store_secrets(
                uow,
                account_id=account.id,
                encryption_key=self.encryption_key,
                password=command.password,
                api_key=command.api_key,
                api_secret=command.api_secret,
                token=command.token,
                key_version=self.encryption_key_version,
                previous_keys=self.previous_encryption_keys,
            )
            await uow.commit()
            dto = BrokerAccountDTO.from_entity(
                account,
                connection=connection,
                credentials=credentials,
            )

        cred_event = CredentialsUpdated(
            broker_account_id=account.id,
            credential_types=tuple(c.credential_type.value for c in credentials),
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.CREATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="broker_account",
                resource_id=account.id,
                actor_user_id=command.user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="Broker account linked",
                metadata={"event_type": cred_event.event_type},
            )
        )
        return dto


@dataclass(frozen=True, slots=True)
class UpdateBrokerAccountUseCase:
    uow_factory: BrokerUnitOfWorkFactory
    audit: RecordAuditEventUseCase
    encryption_key: str
    encryption_key_version: int = 1
    previous_encryption_keys: tuple[str, ...] = ()

    async def execute(self, command: UpdateBrokerAccountCommand) -> BrokerAccountDTO:
        async with self.uow_factory() as uow:
            account = await uow.accounts.get_by_id(command.account_id)
            if account is None or account.user_id != command.user_id:
                raise NotFoundError(
                    "Broker account not found",
                    details={"account_id": str(command.account_id)},
                )
            account.update_fields(
                label=command.label,
                server=command.server,
                environment=command.environment,
                metadata=command.metadata,
            )
            if command.status is not None and command.status != account.status:
                _apply_account_status(account, command.status)
            await uow.accounts.update(account)
            await _store_secrets(
                uow,
                account_id=account.id,
                encryption_key=self.encryption_key,
                password=command.password,
                api_key=command.api_key,
                api_secret=command.api_secret,
                token=command.token,
                key_version=self.encryption_key_version,
                previous_keys=self.previous_encryption_keys,
            )
            connection = await uow.connections.get_for_account(account.id)
            credentials = await uow.credentials.list_for_account(account.id)
            await uow.commit()
            dto = BrokerAccountDTO.from_entity(
                account,
                connection=connection,
                credentials=credentials,
            )

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.UPDATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="broker_account",
                resource_id=account.id,
                actor_user_id=command.user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="Broker account updated",
            )
        )
        return dto


@dataclass(frozen=True, slots=True)
class DeleteBrokerAccountUseCase:
    uow_factory: BrokerUnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(self, command: DeleteBrokerAccountCommand) -> None:
        async with self.uow_factory() as uow:
            account = await uow.accounts.get_by_id(command.account_id)
            if account is None:
                raise NotFoundError(
                    "Broker account not found",
                    details={"account_id": str(command.account_id)},
                )
            if account.user_id != command.user_id:
                raise AuthorizationError(
                    "Cannot delete another user's broker account",
                    details={"account_id": str(command.account_id)},
                )
            account.revoke()
            await uow.accounts.update(account)
            await uow.credentials.delete_for_account(account.id)
            await uow.sessions.delete_for_account(account.id)
            await uow.connections.delete_for_account(account.id)
            await uow.commit()

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.DELETE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="broker_account",
                resource_id=command.account_id,
                actor_user_id=command.user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="Broker account revoked and credentials removed",
            )
        )


def _apply_account_status(account: BrokerAccount, status: BrokerAccountStatus) -> None:
    if status == BrokerAccountStatus.ACTIVE:
        account.activate()
    elif status == BrokerAccountStatus.INACTIVE:
        account.deactivate()
    elif status == BrokerAccountStatus.REVOKED:
        account.revoke()
    elif status == BrokerAccountStatus.PENDING:
        raise ValidationError(
            "Cannot revert broker account status to pending",
            details={"status": status.value},
        )


async def _store_secrets(
    uow: object,
    *,
    account_id: UUID,
    encryption_key: str,
    password: str | None,
    api_key: str | None,
    api_secret: str | None,
    token: str | None,
    key_version: int = 1,
    previous_keys: tuple[str, ...] = (),
) -> list[BrokerCredential]:
    """Encrypt and upsert provided secrets. Never returns plaintext."""
    credentials_repo = uow.credentials  # type: ignore[attr-defined]
    crypto = CredentialEncryptionService(
        secret_key=encryption_key,
        key_version=key_version,
        previous_keys=previous_keys,
    )
    pairs: list[tuple[BrokerCredentialType, str | None]] = [
        (BrokerCredentialType.PASSWORD, password),
        (BrokerCredentialType.API_KEY, api_key),
        (BrokerCredentialType.API_SECRET, api_secret),
        (BrokerCredentialType.TOKEN, token),
    ]
    for cred_type, secret in pairs:
        if secret is None or secret == "":
            continue
        ciphertext, version = crypto.encrypt(secret)
        hint = credential_hint(secret, visible=0)
        existing = await credentials_repo.get_by_account_and_type(account_id, cred_type)
        if existing is None:
            credential = BrokerCredential.store(
                broker_account_id=account_id,
                credential_type=cred_type,
                encrypted_payload=ciphertext,
                key_hint=hint,
                encryption_key_version=version,
            )
            await credentials_repo.add(credential)
        else:
            existing.rotate(
                encrypted_payload=ciphertext,
                key_hint=hint,
                encryption_key_version=version,
            )
            await credentials_repo.update(existing)
    # Return full list for DTO enrichment when creating
    return list(await credentials_repo.list_for_account(account_id))


async def _build_connect_request(
    uow: object,
    *,
    account: BrokerAccount,
    encryption_key: str,
) -> BrokerConnectRequest:
    credentials_repo = uow.credentials  # type: ignore[attr-defined]
    credentials = await credentials_repo.list_for_account(account.id)
    password = ""
    api_key = ""
    api_secret = ""
    token = ""
    for cred in credentials:
        try:
            plaintext = decrypt_secret(
                cred.encrypted_payload, secret_key=encryption_key
            )
        except ValueError as exc:
            raise ValidationError(
                "Failed to decrypt broker credentials",
                details={"credential_type": cred.credential_type.value},
            ) from exc
        if cred.credential_type == BrokerCredentialType.PASSWORD:
            password = plaintext
        elif cred.credential_type == BrokerCredentialType.API_KEY:
            api_key = plaintext
        elif cred.credential_type == BrokerCredentialType.API_SECRET:
            api_secret = plaintext
        elif cred.credential_type == BrokerCredentialType.TOKEN:
            token = plaintext
    return BrokerConnectRequest(
        broker_account_id=account.id,
        external_account_id=account.external_account_id,
        server=account.server,
        password=password,
        api_key=api_key,
        api_secret=api_secret,
        token=token,
    )


async def _record_connection_healthy(
    uow: object,
    *,
    monitor: ConnectionHealthMonitor,
    reconnect: AutomaticReconnectManager,
    connection: BrokerConnection,
    broker_id: UUID,
    account_id: UUID,
) -> None:
    health = monitor.ensure(
        connection_id=connection.id,
        broker_account_id=account_id,
        broker_id=broker_id,
    )
    _, _changed = monitor.mark_connected(connection.id)
    _, _event = reconnect.record_success(connection.id, broker_id=broker_id)
    await uow.health.upsert(health)  # type: ignore[attr-defined]


async def _record_connection_lost(
    uow: object,
    *,
    monitor: ConnectionHealthMonitor,
    reconnect: AutomaticReconnectManager,
    connection: BrokerConnection,
    broker_id: UUID,
    account_id: UUID,
    error: str,
    attempt_reconnect: bool = True,
) -> None:
    health = monitor.ensure(
        connection_id=connection.id,
        broker_account_id=account_id,
        broker_id=broker_id,
    )
    _, _lost = monitor.mark_lost(connection.id, error=error)
    if attempt_reconnect and reconnect.can_attempt(connection.id):
        reconnect.record_attempt(connection.id)
        health.record_reconnect_attempt()
    await uow.health.upsert(health)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class ListBrokerConnectionsUseCase:
    uow_factory: BrokerUnitOfWorkFactory

    async def execute(self, *, user_id: UUID) -> list[BrokerConnectionDTO]:
        async with self.uow_factory() as uow:
            connections = await uow.connections.list_for_user(user_id)
            result: list[BrokerConnectionDTO] = []
            for connection in connections:
                session = await uow.sessions.get_active_for_account(
                    connection.broker_account_id
                )
                result.append(
                    BrokerConnectionDTO.from_entity(
                        connection,
                        session_id=session.id if session else None,
                    )
                )
            return result


@dataclass(frozen=True, slots=True)
class GetBrokerConnectionUseCase:
    uow_factory: BrokerUnitOfWorkFactory

    async def execute(
        self, *, user_id: UUID, connection_id: UUID
    ) -> BrokerConnectionDTO:
        async with self.uow_factory() as uow:
            connection = await uow.connections.get_by_id(connection_id)
            if connection is None:
                raise NotFoundError(
                    "Broker connection not found",
                    details={"connection_id": str(connection_id)},
                )
            account = await uow.accounts.get_by_id(connection.broker_account_id)
            if account is None or account.user_id != user_id:
                raise NotFoundError(
                    "Broker connection not found",
                    details={"connection_id": str(connection_id)},
                )
            session = await uow.sessions.get_active_for_account(account.id)
            return BrokerConnectionDTO.from_entity(
                connection,
                session_id=session.id if session else None,
            )


@dataclass(frozen=True, slots=True)
class ConnectBrokerUseCase:
    """Connect a broker account via the registered adapter (placeholders NYI)."""

    uow_factory: BrokerUnitOfWorkFactory
    audit: RecordAuditEventUseCase
    registry: BrokerRegistryPort
    encryption_key: str
    health_monitor: ConnectionHealthMonitor
    reconnect_manager: AutomaticReconnectManager

    async def execute(self, command: ConnectBrokerCommand) -> BrokerConnectionDTO:
        async with self.uow_factory() as uow:
            account = await uow.accounts.get_by_id(command.account_id)
            if account is None or account.user_id != command.user_id:
                raise NotFoundError(
                    "Broker account not found",
                    details={"account_id": str(command.account_id)},
                )
            broker = await uow.brokers.get_by_id(account.broker_id)
            if broker is None:
                raise NotFoundError(
                    "Broker not found",
                    details={"broker_id": str(account.broker_id)},
                )
            connection = await uow.connections.get_for_account(account.id)
            if connection is None:
                connection = BrokerConnection.create_for_account(
                    broker_account_id=account.id
                )
                await uow.connections.add(connection)

            adapter = self.registry.get(broker.platform_code.value)
            if adapter is None:
                raise ValidationError(
                    "No adapter registered for broker platform",
                    details={"platform_code": broker.platform_code.value},
                )

            connection.mark_connecting()
            await uow.connections.update(connection)
            request = await _build_connect_request(
                uow, account=account, encryption_key=self.encryption_key
            )
            try:
                session_ref = await adapter.connect(request)
            except NotImplementedError as exc:
                connection.mark_error(str(exc))
                await uow.connections.update(connection)
                await _record_connection_lost(
                    uow,
                    monitor=self.health_monitor,
                    reconnect=self.reconnect_manager,
                    connection=connection,
                    broker_id=broker.id,
                    account_id=account.id,
                    error=str(exc),
                )
                await uow.commit()
                raise ValidationError(
                    "Broker adapter is not implemented yet",
                    details={"platform_code": broker.platform_code.value},
                ) from exc
            except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
                connection.mark_error(str(exc))
                await uow.connections.update(connection)
                await _record_connection_lost(
                    uow,
                    monitor=self.health_monitor,
                    reconnect=self.reconnect_manager,
                    connection=connection,
                    broker_id=broker.id,
                    account_id=account.id,
                    error=str(exc),
                )
                await uow.commit()
                raise ValidationError(
                    "Broker connect failed",
                    details={"platform_code": broker.platform_code.value},
                ) from exc

            connection.mark_connected(adapter_session_ref=session_ref)
            await uow.connections.update(connection)
            await _record_connection_healthy(
                uow,
                monitor=self.health_monitor,
                reconnect=self.reconnect_manager,
                connection=connection,
                broker_id=broker.id,
                account_id=account.id,
            )
            existing = await uow.sessions.get_active_for_account(account.id)
            if existing is not None:
                existing.close()
                await uow.sessions.update(existing)
            session = BrokerSession.open(
                broker_account_id=account.id,
                connection_id=connection.id,
                session_ref=session_ref,
            )
            await uow.sessions.add(session)
            if account.status != BrokerAccountStatus.ACTIVE:
                account.activate()
                await uow.accounts.update(account)
            await uow.commit()
            dto = BrokerConnectionDTO.from_entity(connection, session_id=session.id)

        connected = BrokerConnected(
            broker_id=broker.id,
            broker_account_id=account.id,
            connection_id=connection.id,
            session_id=session.id,
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.ACTIVATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="broker_connection",
                resource_id=connection.id,
                actor_user_id=command.user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="Broker account connected",
                metadata={"event_type": connected.event_type},
            )
        )
        return dto


@dataclass(frozen=True, slots=True)
class DisconnectBrokerUseCase:
    uow_factory: BrokerUnitOfWorkFactory
    audit: RecordAuditEventUseCase
    registry: BrokerRegistryPort
    health_monitor: ConnectionHealthMonitor
    reconnect_manager: AutomaticReconnectManager

    async def execute(self, command: DisconnectBrokerCommand) -> BrokerConnectionDTO:
        async with self.uow_factory() as uow:
            account = await uow.accounts.get_by_id(command.account_id)
            if account is None or account.user_id != command.user_id:
                raise NotFoundError(
                    "Broker account not found",
                    details={"account_id": str(command.account_id)},
                )
            broker = await uow.brokers.get_by_id(account.broker_id)
            if broker is None:
                raise NotFoundError(
                    "Broker not found",
                    details={"broker_id": str(account.broker_id)},
                )
            connection = await uow.connections.get_for_account(account.id)
            if connection is None:
                raise NotFoundError(
                    "Broker connection not found",
                    details={"account_id": str(command.account_id)},
                )
            session = await uow.sessions.get_active_for_account(account.id)
            adapter = self.registry.get(broker.platform_code.value)
            if adapter is not None and connection.adapter_session_ref:
                with contextlib.suppress(NotImplementedError):
                    await adapter.disconnect(session_ref=connection.adapter_session_ref)
            if session is not None:
                session.close()
                await uow.sessions.update(session)
            connection.mark_disconnected()
            await uow.connections.update(connection)
            await _record_connection_lost(
                uow,
                monitor=self.health_monitor,
                reconnect=self.reconnect_manager,
                connection=connection,
                broker_id=broker.id,
                account_id=account.id,
                error="disconnected",
                attempt_reconnect=False,
            )
            await uow.commit()
            dto = BrokerConnectionDTO.from_entity(
                connection,
                session_id=session.id if session else None,
            )

        disconnected = BrokerDisconnected(
            broker_id=broker.id,
            broker_account_id=account.id,
            connection_id=connection.id,
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.DEACTIVATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="broker_connection",
                resource_id=connection.id,
                actor_user_id=command.user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="Broker account disconnected",
                metadata={"event_type": disconnected.event_type},
            )
        )
        return dto


@dataclass(frozen=True, slots=True)
class ValidateBrokerUseCase:
    uow_factory: BrokerUnitOfWorkFactory
    audit: RecordAuditEventUseCase
    registry: BrokerRegistryPort
    encryption_key: str

    async def execute(self, command: ValidateBrokerCommand) -> ValidateBrokerResultDTO:
        async with self.uow_factory() as uow:
            account = await uow.accounts.get_by_id(command.account_id)
            if account is None or account.user_id != command.user_id:
                raise NotFoundError(
                    "Broker account not found",
                    details={"account_id": str(command.account_id)},
                )
            broker = await uow.brokers.get_by_id(account.broker_id)
            if broker is None:
                raise NotFoundError(
                    "Broker not found",
                    details={"broker_id": str(account.broker_id)},
                )
            adapter = self.registry.get(broker.platform_code.value)
            if adapter is None:
                raise ValidationError(
                    "No adapter registered for broker platform",
                    details={"platform_code": broker.platform_code.value},
                )
            request = await _build_connect_request(
                uow, account=account, encryption_key=self.encryption_key
            )
            try:
                valid = await adapter.validate_credentials(request)
            except NotImplementedError as exc:
                raise ValidationError(
                    "Broker adapter is not implemented yet",
                    details={"platform_code": broker.platform_code.value},
                ) from exc
            except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
                raise ValidationError(
                    "Broker credential validation failed",
                    details={
                        "platform_code": broker.platform_code.value,
                        "reason": str(exc),
                    },
                ) from exc

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.READ,
                outcome=(AuditOutcome.SUCCESS if valid else AuditOutcome.FAILURE),
                resource_type="broker_account",
                resource_id=account.id,
                actor_user_id=command.user_id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                message="Broker credentials validated",
            )
        )
        return ValidateBrokerResultDTO(
            account_id=account.id,
            valid=bool(valid),
            platform_code=broker.platform_code.value,
            message="ok" if valid else "invalid",
        )
