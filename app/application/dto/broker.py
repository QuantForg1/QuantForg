"""Application DTOs and commands for Broker Foundation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.broker import Broker
from app.domain.entities.broker_integration import (
    BrokerAccount,
    BrokerCapability,
    BrokerConnection,
    BrokerCredential,
)
from app.domain.enums.broker import (
    BrokerAccountStatus,
    BrokerCapabilityCode,
    BrokerEnvironment,
    BrokerPlatform,
    BrokerStatus,
    BrokerType,
)


@dataclass(frozen=True, slots=True)
class BrokerDTO:
    id: UUID
    name: str
    slug: str
    broker_type: str
    status: str
    platform_code: str
    country_code: str
    website: str
    description: str
    created_at: datetime
    updated_at: datetime
    capabilities: tuple[str, ...] = ()

    @classmethod
    def from_entity(
        cls,
        broker: Broker,
        *,
        capabilities: list[BrokerCapability] | None = None,
    ) -> BrokerDTO:
        caps = tuple(c.code.value for c in (capabilities or []) if c.enabled)
        return cls(
            id=broker.id,
            name=str(broker.name),
            slug=str(broker.slug),
            broker_type=broker.broker_type.value,
            status=broker.status.value,
            platform_code=broker.platform_code.value,
            country_code=broker.country_code,
            website=broker.website,
            description=broker.description,
            created_at=broker.created_at,
            updated_at=broker.updated_at,
            capabilities=caps,
        )


@dataclass(frozen=True, slots=True)
class BrokerAccountDTO:
    id: UUID
    user_id: UUID
    broker_id: UUID
    external_account_id: str
    label: str
    environment: str
    status: str
    server: str
    metadata: dict[str, str]
    created_at: datetime
    updated_at: datetime
    connection_status: str | None = None
    credential_types: tuple[str, ...] = ()

    @classmethod
    def from_entity(
        cls,
        account: BrokerAccount,
        *,
        connection: BrokerConnection | None = None,
        credentials: list[BrokerCredential] | None = None,
    ) -> BrokerAccountDTO:
        return cls(
            id=account.id,
            user_id=account.user_id,
            broker_id=account.broker_id,
            external_account_id=account.external_account_id,
            label=account.label,
            environment=account.environment.value,
            status=account.status.value,
            server=account.server,
            metadata=dict(account.metadata),
            created_at=account.created_at,
            updated_at=account.updated_at,
            connection_status=connection.status.value if connection else None,
            credential_types=tuple(
                c.credential_type.value for c in (credentials or [])
            ),
        )


@dataclass(frozen=True, slots=True)
class CredentialMetaDTO:
    """Public credential metadata — never includes secrets or ciphertext."""

    id: UUID
    broker_account_id: UUID
    credential_type: str
    key_hint: str
    has_secret: bool
    rotated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, credential: BrokerCredential) -> CredentialMetaDTO:
        return cls(
            id=credential.id,
            broker_account_id=credential.broker_account_id,
            credential_type=credential.credential_type.value,
            key_hint=credential.key_hint,
            has_secret=True,
            rotated_at=credential.rotated_at,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
        )


@dataclass(frozen=True, slots=True)
class CreateBrokerCommand:
    name: str
    slug: str
    broker_type: BrokerType = BrokerType.RETAIL
    platform_code: BrokerPlatform = BrokerPlatform.OTHER
    country_code: str = "US"
    website: str = ""
    description: str = ""
    activate: bool = True
    capability_codes: tuple[BrokerCapabilityCode, ...] = ()
    actor_user_id: UUID | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class UpdateBrokerCommand:
    broker_id: UUID
    name: str | None = None
    broker_type: BrokerType | None = None
    platform_code: BrokerPlatform | None = None
    country_code: str | None = None
    website: str | None = None
    description: str | None = None
    status: BrokerStatus | None = None
    actor_user_id: UUID | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class DeleteBrokerCommand:
    broker_id: UUID
    actor_user_id: UUID | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class CreateBrokerAccountCommand:
    user_id: UUID
    broker_id: UUID
    external_account_id: str
    label: str = ""
    environment: BrokerEnvironment = BrokerEnvironment.DEMO
    server: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    password: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    token: str | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class UpdateBrokerAccountCommand:
    user_id: UUID
    account_id: UUID
    label: str | None = None
    server: str | None = None
    environment: BrokerEnvironment | None = None
    metadata: dict[str, str] | None = None
    status: BrokerAccountStatus | None = None
    password: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    token: str | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class DeleteBrokerAccountCommand:
    user_id: UUID
    account_id: UUID
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class BrokerConnectionDTO:
    id: UUID
    broker_account_id: UUID
    status: str
    last_connected_at: datetime | None
    last_error: str
    adapter_session_ref: str
    created_at: datetime
    updated_at: datetime
    session_id: UUID | None = None

    @classmethod
    def from_entity(
        cls,
        connection: BrokerConnection,
        *,
        session_id: UUID | None = None,
    ) -> BrokerConnectionDTO:
        return cls(
            id=connection.id,
            broker_account_id=connection.broker_account_id,
            status=connection.status.value,
            last_connected_at=connection.last_connected_at,
            last_error=connection.last_error,
            adapter_session_ref=connection.adapter_session_ref,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
            session_id=session_id,
        )


@dataclass(frozen=True, slots=True)
class ConnectBrokerCommand:
    user_id: UUID
    account_id: UUID
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class DisconnectBrokerCommand:
    user_id: UUID
    account_id: UUID
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class ValidateBrokerCommand:
    user_id: UUID
    account_id: UUID
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class ValidateBrokerResultDTO:
    account_id: UUID
    valid: bool
    platform_code: str
    message: str = ""
