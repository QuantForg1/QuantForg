"""Postgres persistence for Broker Foundation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.domain.entities.broker import Broker
from app.domain.entities.broker_health import BrokerConnectionHealth
from app.domain.entities.broker_integration import (
    BrokerAccount,
    BrokerCapability,
    BrokerConnection,
    BrokerCredential,
    BrokerSession,
)
from app.domain.enums.broker import (
    BrokerAccountStatus,
    BrokerCapabilityCode,
    BrokerConnectionStatus,
    BrokerCredentialType,
    BrokerEnvironment,
    BrokerHealthStatus,
    BrokerPlatform,
    BrokerStatus,
    BrokerType,
    CredentialStatus,
)
from app.domain.value_objects.identity import EntitySlug, PersonName
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    parse_datetime,
    parse_datetime_optional,
    parse_uuid,
)
from app.infrastructure.persistence.postgres_platform import PostgresAuditLogRepository
from core.database.session import DatabaseManager


def _broker_from_row(row: Any) -> Broker:
    return Broker(
        id=parse_uuid(row["id"]),
        name=PersonName(value=str(row["name"])),
        slug=EntitySlug(value=str(row["slug"])),
        broker_type=BrokerType(str(row["broker_type"])),
        status=BrokerStatus(str(row["status"])),
        platform_code=BrokerPlatform(str(row.get("platform_code") or "other")),
        country_code=str(row["country_code"] or ""),
        website=str(row["website"] or ""),
        description=str(row.get("description") or ""),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _capability_from_row(row: Any) -> BrokerCapability:
    return BrokerCapability(
        id=parse_uuid(row["id"]),
        broker_id=parse_uuid(row["broker_id"]),
        code=BrokerCapabilityCode(str(row["code"])),
        enabled=bool(row["enabled"]),
        notes=str(row["notes"] or ""),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _account_from_row(row: Any) -> BrokerAccount:
    meta_raw = json_dict(row["metadata"])
    return BrokerAccount(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        broker_id=parse_uuid(row["broker_id"]),
        external_account_id=str(row["external_account_id"]),
        label=str(row["label"] or ""),
        environment=BrokerEnvironment(str(row["environment"])),
        status=BrokerAccountStatus(str(row["status"])),
        server=str(row["server"] or ""),
        metadata={str(k): str(v) for k, v in meta_raw.items()},
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _credential_from_row(row: Any) -> BrokerCredential:
    return BrokerCredential(
        id=parse_uuid(row["id"]),
        broker_account_id=parse_uuid(row["broker_account_id"]),
        credential_type=BrokerCredentialType(str(row["credential_type"])),
        encrypted_payload=str(row["encrypted_payload"]),
        key_hint=str(row["key_hint"] or ""),
        status=CredentialStatus(str(row.get("status") or "active")),
        encryption_key_version=int(row.get("encryption_key_version") or 1),
        rotated_at=parse_datetime_optional(row["rotated_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _connection_from_row(row: Any) -> BrokerConnection:
    return BrokerConnection(
        id=parse_uuid(row["id"]),
        broker_account_id=parse_uuid(row["broker_account_id"]),
        status=BrokerConnectionStatus(str(row["status"])),
        last_connected_at=parse_datetime_optional(row["last_connected_at"]),
        last_error=str(row["last_error"] or ""),
        adapter_session_ref=str(row["adapter_session_ref"] or ""),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _session_from_row(row: Any) -> BrokerSession:
    return BrokerSession(
        id=parse_uuid(row["id"]),
        broker_account_id=parse_uuid(row["broker_account_id"]),
        connection_id=parse_uuid(row["connection_id"]),
        session_ref=str(row["session_ref"]),
        status=BrokerConnectionStatus(str(row["status"])),
        expires_at=parse_datetime_optional(row["expires_at"]),
        last_refreshed_at=parse_datetime_optional(row["last_refreshed_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _health_from_row(row: Any) -> BrokerConnectionHealth:
    return BrokerConnectionHealth(
        id=parse_uuid(row["id"]),
        connection_id=parse_uuid(row["connection_id"]),
        broker_account_id=parse_uuid(row["broker_account_id"]),
        broker_id=parse_uuid(row["broker_id"]),
        status=BrokerHealthStatus(str(row["status"])),
        latency_ms=(
            float(row["latency_ms"]) if row["latency_ms"] is not None else None
        ),
        last_heartbeat_at=parse_datetime_optional(row["last_heartbeat_at"]),
        last_successful_connection_at=parse_datetime_optional(
            row["last_successful_connection_at"]
        ),
        reconnect_attempts=int(row["reconnect_attempts"] or 0),
        connected_since=parse_datetime_optional(row["connected_since"]),
        last_error=str(row["last_error"] or ""),
        uptime_seconds=float(row["uptime_seconds"] or 0),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


class PostgresBrokerCatalogueRepository:
    def __init__(self, uow: PostgresBrokerUnitOfWork) -> None:
        self._uow = uow

    async def get_by_id(self, broker_id: UUID) -> Broker | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM brokers WHERE id = :id"),
            {"id": str(broker_id)},
        )
        row = result.mappings().first()
        return _broker_from_row(row) if row else None

    async def get_by_slug(self, slug: EntitySlug) -> Broker | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM brokers WHERE lower(slug) = lower(:slug)"),
            {"slug": str(slug)},
        )
        row = result.mappings().first()
        return _broker_from_row(row) if row else None

    async def list_all(self) -> list[Broker]:
        session = self._uow._require_session()
        result = await session.execute(text("SELECT * FROM brokers ORDER BY name"))
        return [_broker_from_row(r) for r in result.mappings().all()]

    async def add(self, broker: Broker) -> Broker:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO brokers (
                    id, name, slug, broker_type, status, platform_code,
                    country_code, website, description, created_at, updated_at
                ) VALUES (
                    :id, :name, :slug, :broker_type, :status, :platform_code,
                    :country_code, :website, :description, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    slug = EXCLUDED.slug,
                    broker_type = EXCLUDED.broker_type,
                    status = EXCLUDED.status,
                    platform_code = EXCLUDED.platform_code,
                    country_code = EXCLUDED.country_code,
                    website = EXCLUDED.website,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(broker.id),
                "name": str(broker.name),
                "slug": str(broker.slug),
                "broker_type": broker.broker_type.value,
                "status": broker.status.value,
                "platform_code": broker.platform_code.value,
                "country_code": broker.country_code,
                "website": broker.website,
                "description": broker.description,
                "created_at": broker.created_at,
                "updated_at": broker.updated_at,
            },
        )
        return broker

    async def update(self, broker: Broker) -> Broker:
        return await self.add(broker)

    async def delete(self, broker_id: UUID) -> None:
        session = self._uow._require_session()
        await session.execute(
            text("DELETE FROM brokers WHERE id = :id"),
            {"id": str(broker_id)},
        )


class PostgresBrokerCapabilityRepository:
    def __init__(self, uow: PostgresBrokerUnitOfWork) -> None:
        self._uow = uow

    async def list_for_broker(self, broker_id: UUID) -> list[BrokerCapability]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_capabilities
                WHERE broker_id = :broker_id
                ORDER BY code
                """
            ),
            {"broker_id": str(broker_id)},
        )
        return [_capability_from_row(r) for r in result.mappings().all()]

    async def get_by_broker_and_code(
        self, broker_id: UUID, code: BrokerCapabilityCode
    ) -> BrokerCapability | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_capabilities
                WHERE broker_id = :broker_id AND code = :code
                LIMIT 1
                """
            ),
            {"broker_id": str(broker_id), "code": code.value},
        )
        row = result.mappings().first()
        return _capability_from_row(row) if row else None

    async def add(self, capability: BrokerCapability) -> BrokerCapability:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO broker_capabilities (
                    id, broker_id, code, enabled, notes, created_at, updated_at
                ) VALUES (
                    :id, :broker_id, :code, :enabled, :notes, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    broker_id = EXCLUDED.broker_id,
                    code = EXCLUDED.code,
                    enabled = EXCLUDED.enabled,
                    notes = EXCLUDED.notes,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(capability.id),
                "broker_id": str(capability.broker_id),
                "code": capability.code.value,
                "enabled": capability.enabled,
                "notes": capability.notes,
                "created_at": capability.created_at,
                "updated_at": capability.updated_at,
            },
        )
        return capability

    async def update(self, capability: BrokerCapability) -> BrokerCapability:
        return await self.add(capability)

    async def delete(self, capability_id: UUID) -> None:
        session = self._uow._require_session()
        await session.execute(
            text("DELETE FROM broker_capabilities WHERE id = :id"),
            {"id": str(capability_id)},
        )


class PostgresBrokerAccountRepository:
    def __init__(self, uow: PostgresBrokerUnitOfWork) -> None:
        self._uow = uow

    async def get_by_id(self, account_id: UUID) -> BrokerAccount | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM broker_accounts WHERE id = :id"),
            {"id": str(account_id)},
        )
        row = result.mappings().first()
        return _account_from_row(row) if row else None

    async def list_all(self) -> list[BrokerAccount]:
        session = self._uow._require_session()
        result = await session.execute(text("SELECT * FROM broker_accounts"))
        return [_account_from_row(r) for r in result.mappings().all()]

    async def list_for_user(self, user_id: UUID) -> list[BrokerAccount]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_accounts
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                """
            ),
            {"user_id": str(user_id)},
        )
        return [_account_from_row(r) for r in result.mappings().all()]

    async def get_by_user_broker_external(
        self,
        user_id: UUID,
        broker_id: UUID,
        external_account_id: str,
    ) -> BrokerAccount | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_accounts
                WHERE user_id = :user_id
                  AND broker_id = :broker_id
                  AND lower(external_account_id) = lower(:external_account_id)
                LIMIT 1
                """
            ),
            {
                "user_id": str(user_id),
                "broker_id": str(broker_id),
                "external_account_id": external_account_id.strip(),
            },
        )
        row = result.mappings().first()
        return _account_from_row(row) if row else None

    async def add(self, account: BrokerAccount) -> BrokerAccount:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO broker_accounts (
                    id, user_id, broker_id, external_account_id, label, environment,
                    status, server, metadata, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :broker_id, :external_account_id, :label,
                    :environment, :status, :server, CAST(:metadata AS jsonb),
                    :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    broker_id = EXCLUDED.broker_id,
                    external_account_id = EXCLUDED.external_account_id,
                    label = EXCLUDED.label,
                    environment = EXCLUDED.environment,
                    status = EXCLUDED.status,
                    server = EXCLUDED.server,
                    metadata = EXCLUDED.metadata,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(account.id),
                "user_id": str(account.user_id),
                "broker_id": str(account.broker_id),
                "external_account_id": account.external_account_id,
                "label": account.label,
                "environment": account.environment.value,
                "status": account.status.value,
                "server": account.server,
                "metadata": as_json(account.metadata),
                "created_at": account.created_at,
                "updated_at": account.updated_at,
            },
        )
        return account

    async def update(self, account: BrokerAccount) -> BrokerAccount:
        return await self.add(account)

    async def delete(self, account_id: UUID) -> None:
        session = self._uow._require_session()
        await session.execute(
            text("DELETE FROM broker_accounts WHERE id = :id"),
            {"id": str(account_id)},
        )


class PostgresBrokerCredentialRepository:
    def __init__(self, uow: PostgresBrokerUnitOfWork) -> None:
        self._uow = uow

    async def get_by_id(self, credential_id: UUID) -> BrokerCredential | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM broker_credentials WHERE id = :id"),
            {"id": str(credential_id)},
        )
        row = result.mappings().first()
        return _credential_from_row(row) if row else None

    async def list_for_account(self, broker_account_id: UUID) -> list[BrokerCredential]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_credentials
                WHERE broker_account_id = :broker_account_id
                """
            ),
            {"broker_account_id": str(broker_account_id)},
        )
        return [_credential_from_row(r) for r in result.mappings().all()]

    async def get_by_account_and_type(
        self,
        broker_account_id: UUID,
        credential_type: BrokerCredentialType,
    ) -> BrokerCredential | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_credentials
                WHERE broker_account_id = :broker_account_id
                  AND credential_type = :credential_type
                LIMIT 1
                """
            ),
            {
                "broker_account_id": str(broker_account_id),
                "credential_type": credential_type.value,
            },
        )
        row = result.mappings().first()
        return _credential_from_row(row) if row else None

    async def add(self, credential: BrokerCredential) -> BrokerCredential:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO broker_credentials (
                    id, broker_account_id, credential_type, encrypted_payload,
                    key_hint, status, encryption_key_version, rotated_at,
                    created_at, updated_at
                ) VALUES (
                    :id, :broker_account_id, :credential_type, :encrypted_payload,
                    :key_hint, :status, :encryption_key_version, :rotated_at,
                    :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    broker_account_id = EXCLUDED.broker_account_id,
                    credential_type = EXCLUDED.credential_type,
                    encrypted_payload = EXCLUDED.encrypted_payload,
                    key_hint = EXCLUDED.key_hint,
                    status = EXCLUDED.status,
                    encryption_key_version = EXCLUDED.encryption_key_version,
                    rotated_at = EXCLUDED.rotated_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(credential.id),
                "broker_account_id": str(credential.broker_account_id),
                "credential_type": credential.credential_type.value,
                "encrypted_payload": credential.encrypted_payload,
                "key_hint": credential.key_hint,
                "status": credential.status.value,
                "encryption_key_version": credential.encryption_key_version,
                "rotated_at": credential.rotated_at,
                "created_at": credential.created_at,
                "updated_at": credential.updated_at,
            },
        )
        return credential

    async def update(self, credential: BrokerCredential) -> BrokerCredential:
        return await self.add(credential)

    async def delete(self, credential_id: UUID) -> None:
        session = self._uow._require_session()
        await session.execute(
            text("DELETE FROM broker_credentials WHERE id = :id"),
            {"id": str(credential_id)},
        )

    async def delete_for_account(self, broker_account_id: UUID) -> None:
        session = self._uow._require_session()
        await session.execute(
            text("DELETE FROM broker_credentials WHERE broker_account_id = :id"),
            {"id": str(broker_account_id)},
        )


class PostgresBrokerConnectionRepository:
    def __init__(self, uow: PostgresBrokerUnitOfWork) -> None:
        self._uow = uow

    async def get_by_id(self, connection_id: UUID) -> BrokerConnection | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM broker_connections WHERE id = :id"),
            {"id": str(connection_id)},
        )
        row = result.mappings().first()
        return _connection_from_row(row) if row else None

    async def get_for_account(self, broker_account_id: UUID) -> BrokerConnection | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_connections
                WHERE broker_account_id = :broker_account_id
                LIMIT 1
                """
            ),
            {"broker_account_id": str(broker_account_id)},
        )
        row = result.mappings().first()
        return _connection_from_row(row) if row else None

    async def list_for_user(self, user_id: UUID) -> list[BrokerConnection]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT c.* FROM broker_connections c
                INNER JOIN broker_accounts a ON a.id = c.broker_account_id
                WHERE a.user_id = :user_id
                ORDER BY c.updated_at DESC
                """
            ),
            {"user_id": str(user_id)},
        )
        return [_connection_from_row(r) for r in result.mappings().all()]

    async def add(self, connection: BrokerConnection) -> BrokerConnection:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO broker_connections (
                    id, broker_account_id, status, last_connected_at, last_error,
                    adapter_session_ref, created_at, updated_at
                ) VALUES (
                    :id, :broker_account_id, :status, :last_connected_at, :last_error,
                    :adapter_session_ref, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    broker_account_id = EXCLUDED.broker_account_id,
                    status = EXCLUDED.status,
                    last_connected_at = EXCLUDED.last_connected_at,
                    last_error = EXCLUDED.last_error,
                    adapter_session_ref = EXCLUDED.adapter_session_ref,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(connection.id),
                "broker_account_id": str(connection.broker_account_id),
                "status": connection.status.value,
                "last_connected_at": connection.last_connected_at,
                "last_error": connection.last_error,
                "adapter_session_ref": connection.adapter_session_ref,
                "created_at": connection.created_at,
                "updated_at": connection.updated_at,
            },
        )
        return connection

    async def update(self, connection: BrokerConnection) -> BrokerConnection:
        return await self.add(connection)

    async def delete_for_account(self, broker_account_id: UUID) -> None:
        session = self._uow._require_session()
        await session.execute(
            text("DELETE FROM broker_connections WHERE broker_account_id = :id"),
            {"id": str(broker_account_id)},
        )


class PostgresBrokerSessionRepository:
    def __init__(self, uow: PostgresBrokerUnitOfWork) -> None:
        self._uow = uow

    async def get_by_id(self, session_id: UUID) -> BrokerSession | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM broker_sessions WHERE id = :id"),
            {"id": str(session_id)},
        )
        row = result.mappings().first()
        return _session_from_row(row) if row else None

    async def get_active_for_account(
        self, broker_account_id: UUID
    ) -> BrokerSession | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_sessions
                WHERE broker_account_id = :broker_account_id
                  AND status = 'connected'
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"broker_account_id": str(broker_account_id)},
        )
        row = result.mappings().first()
        return _session_from_row(row) if row else None

    async def list_for_account(self, broker_account_id: UUID) -> list[BrokerSession]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_sessions
                WHERE broker_account_id = :broker_account_id
                ORDER BY created_at DESC
                """
            ),
            {"broker_account_id": str(broker_account_id)},
        )
        return [_session_from_row(r) for r in result.mappings().all()]

    async def add(self, broker_session: BrokerSession) -> BrokerSession:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO broker_sessions (
                    id, broker_account_id, connection_id, session_ref, status,
                    expires_at, last_refreshed_at, created_at, updated_at
                ) VALUES (
                    :id, :broker_account_id, :connection_id, :session_ref, :status,
                    :expires_at, :last_refreshed_at, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    broker_account_id = EXCLUDED.broker_account_id,
                    connection_id = EXCLUDED.connection_id,
                    session_ref = EXCLUDED.session_ref,
                    status = EXCLUDED.status,
                    expires_at = EXCLUDED.expires_at,
                    last_refreshed_at = EXCLUDED.last_refreshed_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(broker_session.id),
                "broker_account_id": str(broker_session.broker_account_id),
                "connection_id": str(broker_session.connection_id),
                "session_ref": broker_session.session_ref,
                "status": broker_session.status.value,
                "expires_at": broker_session.expires_at,
                "last_refreshed_at": broker_session.last_refreshed_at,
                "created_at": broker_session.created_at,
                "updated_at": broker_session.updated_at,
            },
        )
        return broker_session

    async def update(self, broker_session: BrokerSession) -> BrokerSession:
        return await self.add(broker_session)

    async def delete_for_account(self, broker_account_id: UUID) -> None:
        session = self._uow._require_session()
        await session.execute(
            text("DELETE FROM broker_sessions WHERE broker_account_id = :id"),
            {"id": str(broker_account_id)},
        )


class PostgresBrokerConnectionHealthRepository:
    def __init__(self, uow: PostgresBrokerUnitOfWork) -> None:
        self._uow = uow

    async def get_by_connection_id(
        self, connection_id: UUID
    ) -> BrokerConnectionHealth | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_connection_health
                WHERE connection_id = :connection_id
                LIMIT 1
                """
            ),
            {"connection_id": str(connection_id)},
        )
        row = result.mappings().first()
        return _health_from_row(row) if row else None

    async def list_for_broker(self, broker_id: UUID) -> list[BrokerConnectionHealth]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_connection_health
                WHERE broker_id = :broker_id
                """
            ),
            {"broker_id": str(broker_id)},
        )
        return [_health_from_row(r) for r in result.mappings().all()]

    async def list_for_account(
        self, broker_account_id: UUID
    ) -> list[BrokerConnectionHealth]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM broker_connection_health
                WHERE broker_account_id = :broker_account_id
                """
            ),
            {"broker_account_id": str(broker_account_id)},
        )
        return [_health_from_row(r) for r in result.mappings().all()]

    async def add(self, health: BrokerConnectionHealth) -> BrokerConnectionHealth:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO broker_connection_health (
                    id, connection_id, broker_account_id, broker_id, status,
                    latency_ms, last_heartbeat_at, last_successful_connection_at,
                    reconnect_attempts, connected_since, last_error, uptime_seconds,
                    created_at, updated_at
                ) VALUES (
                    :id, :connection_id, :broker_account_id, :broker_id, :status,
                    :latency_ms, :last_heartbeat_at, :last_successful_connection_at,
                    :reconnect_attempts, :connected_since, :last_error,
                    :uptime_seconds, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    connection_id = EXCLUDED.connection_id,
                    broker_account_id = EXCLUDED.broker_account_id,
                    broker_id = EXCLUDED.broker_id,
                    status = EXCLUDED.status,
                    latency_ms = EXCLUDED.latency_ms,
                    last_heartbeat_at = EXCLUDED.last_heartbeat_at,
                    last_successful_connection_at =
                        EXCLUDED.last_successful_connection_at,
                    reconnect_attempts = EXCLUDED.reconnect_attempts,
                    connected_since = EXCLUDED.connected_since,
                    last_error = EXCLUDED.last_error,
                    uptime_seconds = EXCLUDED.uptime_seconds,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(health.id),
                "connection_id": str(health.connection_id),
                "broker_account_id": str(health.broker_account_id),
                "broker_id": str(health.broker_id),
                "status": health.status.value,
                "latency_ms": health.latency_ms,
                "last_heartbeat_at": health.last_heartbeat_at,
                "last_successful_connection_at": health.last_successful_connection_at,
                "reconnect_attempts": health.reconnect_attempts,
                "connected_since": health.connected_since,
                "last_error": health.last_error,
                "uptime_seconds": health.uptime_seconds,
                "created_at": health.created_at,
                "updated_at": health.updated_at,
            },
        )
        return health

    async def update(self, health: BrokerConnectionHealth) -> BrokerConnectionHealth:
        return await self.add(health)

    async def upsert(self, health: BrokerConnectionHealth) -> BrokerConnectionHealth:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                INSERT INTO broker_connection_health (
                    id, connection_id, broker_account_id, broker_id, status,
                    latency_ms, last_heartbeat_at, last_successful_connection_at,
                    reconnect_attempts, connected_since, last_error, uptime_seconds,
                    created_at, updated_at
                ) VALUES (
                    :id, :connection_id, :broker_account_id, :broker_id, :status,
                    :latency_ms, :last_heartbeat_at, :last_successful_connection_at,
                    :reconnect_attempts, :connected_since, :last_error,
                    :uptime_seconds, :created_at, :updated_at
                )
                ON CONFLICT (connection_id) DO UPDATE SET
                    broker_account_id = EXCLUDED.broker_account_id,
                    broker_id = EXCLUDED.broker_id,
                    status = EXCLUDED.status,
                    latency_ms = EXCLUDED.latency_ms,
                    last_heartbeat_at = EXCLUDED.last_heartbeat_at,
                    last_successful_connection_at =
                        EXCLUDED.last_successful_connection_at,
                    reconnect_attempts = EXCLUDED.reconnect_attempts,
                    connected_since = EXCLUDED.connected_since,
                    last_error = EXCLUDED.last_error,
                    uptime_seconds = EXCLUDED.uptime_seconds,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
                """
            ),
            {
                "id": str(health.id),
                "connection_id": str(health.connection_id),
                "broker_account_id": str(health.broker_account_id),
                "broker_id": str(health.broker_id),
                "status": health.status.value,
                "latency_ms": health.latency_ms,
                "last_heartbeat_at": health.last_heartbeat_at,
                "last_successful_connection_at": health.last_successful_connection_at,
                "reconnect_attempts": health.reconnect_attempts,
                "connected_since": health.connected_since,
                "last_error": health.last_error,
                "uptime_seconds": health.uptime_seconds,
                "created_at": health.created_at,
                "updated_at": health.updated_at,
            },
        )
        row = result.mappings().first()
        if row:
            health.id = parse_uuid(row["id"])
        return health


class PostgresBrokerUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.brokers = PostgresBrokerCatalogueRepository(self)
        self.capabilities = PostgresBrokerCapabilityRepository(self)
        self.accounts = PostgresBrokerAccountRepository(self)
        self.credentials = PostgresBrokerCredentialRepository(self)
        self.connections = PostgresBrokerConnectionRepository(self)
        self.sessions = PostgresBrokerSessionRepository(self)
        self.health = PostgresBrokerConnectionHealthRepository(self)
        self.audit_logs = PostgresAuditLogRepository(self)


class PostgresBrokerUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresBrokerUnitOfWork:
        return PostgresBrokerUnitOfWork(self._database)
