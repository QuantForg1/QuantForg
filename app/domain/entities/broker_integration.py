"""Broker integration aggregates — accounts, credentials, connections, capabilities.

These entities model how QuantForg links a user to a broker venue and tracks
adapter connection state. They do **not** execute trades or talk to MT5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.broker import (
    BrokerAccountStatus,
    BrokerCapabilityCode,
    BrokerConnectionStatus,
    BrokerCredentialType,
    BrokerEnvironment,
    CredentialStatus,
)


@dataclass(eq=False, kw_only=True)
class BrokerCapability(Entity):
    """Advertised capability for a broker / platform adapter."""

    broker_id: UUID
    code: BrokerCapabilityCode
    enabled: bool = True
    notes: str = ""

    def __post_init__(self) -> None:
        self.notes = self.notes.strip()

    @classmethod
    def declare(
        cls,
        *,
        broker_id: UUID,
        code: BrokerCapabilityCode,
        enabled: bool = True,
        notes: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "broker_id": broker_id,
            "code": code,
            "enabled": enabled,
            "notes": notes.strip(),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def enable(self) -> None:
        self.enabled = True
        self.touch()

    def disable(self) -> None:
        self.enabled = False
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "broker_id": str(self.broker_id),
                "code": self.code.value,
                "enabled": self.enabled,
                "notes": self.notes,
            }
        )
        return base


@dataclass(eq=False, kw_only=True)
class BrokerAccount(Entity):
    """User-owned link to an external broker account (integration layer).

    Distinct from :class:`TradingAccount`, which models trading balance and
    lifecycle for the trading domain. BrokerAccount is the adapter-facing
    identity (login, server, environment).
    """

    user_id: UUID
    broker_id: UUID
    external_account_id: str
    label: str = ""
    environment: BrokerEnvironment = BrokerEnvironment.DEMO
    status: BrokerAccountStatus = BrokerAccountStatus.PENDING
    server: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._normalize()
        self._validate()

    def _normalize(self) -> None:
        self.external_account_id = self.external_account_id.strip()
        self.label = self.label.strip()
        self.server = self.server.strip()

    def _validate(self) -> None:
        require(
            len(self.external_account_id) > 0,
            "external_account_id is required",
        )
        require(
            len(self.external_account_id) <= 128,
            "external_account_id must be at most 128 characters",
        )

    @classmethod
    def link(
        cls,
        *,
        user_id: UUID,
        broker_id: UUID,
        external_account_id: str,
        label: str = "",
        environment: BrokerEnvironment = BrokerEnvironment.DEMO,
        server: str = "",
        metadata: dict[str, str] | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "broker_id": broker_id,
            "external_account_id": external_account_id,
            "label": label,
            "environment": environment,
            "status": BrokerAccountStatus.PENDING,
            "server": server,
            "metadata": dict(metadata or {}),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def activate(self) -> None:
        require_state(
            self.status in {BrokerAccountStatus.PENDING, BrokerAccountStatus.INACTIVE},
            "Only pending or inactive broker accounts can be activated",
            status=self.status.value,
        )
        self.status = BrokerAccountStatus.ACTIVE
        self.touch()

    def deactivate(self) -> None:
        require_state(
            self.status == BrokerAccountStatus.ACTIVE,
            "Only active broker accounts can be deactivated",
            status=self.status.value,
        )
        self.status = BrokerAccountStatus.INACTIVE
        self.touch()

    def revoke(self) -> None:
        require_state(
            self.status != BrokerAccountStatus.REVOKED,
            "Broker account is already revoked",
            status=self.status.value,
        )
        self.status = BrokerAccountStatus.REVOKED
        self.touch()

    def update_fields(
        self,
        *,
        label: str | None = None,
        server: str | None = None,
        environment: BrokerEnvironment | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        require_state(
            self.status != BrokerAccountStatus.REVOKED,
            "Cannot update a revoked broker account",
            status=self.status.value,
        )
        if label is not None:
            self.label = label
        if server is not None:
            self.server = server
        if environment is not None:
            self.environment = environment
        if metadata is not None:
            self.metadata = dict(metadata)
        self._normalize()
        self._validate()
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "broker_id": str(self.broker_id),
                "external_account_id": self.external_account_id,
                "label": self.label,
                "environment": self.environment.value,
                "status": self.status.value,
                "server": self.server,
                "metadata": dict(self.metadata),
            }
        )
        return base


@dataclass(eq=False, kw_only=True)
class BrokerCredential(Entity):
    """Encrypted credential material for a broker account.

    The plaintext secret never lives on this entity after construction —
    only ``encrypted_payload`` is persisted. API responses must never expose
    the ciphertext or any recovered secret.
    """

    broker_account_id: UUID
    credential_type: BrokerCredentialType
    encrypted_payload: str
    key_hint: str = ""
    status: CredentialStatus = CredentialStatus.ACTIVE
    rotated_at: datetime | None = None

    def __post_init__(self) -> None:
        require(
            len(self.encrypted_payload) > 0,
            "encrypted_payload is required",
        )
        self.key_hint = self.key_hint.strip()[:32]

    @classmethod
    def store(
        cls,
        *,
        broker_account_id: UUID,
        credential_type: BrokerCredentialType,
        encrypted_payload: str,
        key_hint: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "broker_account_id": broker_account_id,
            "credential_type": credential_type,
            "encrypted_payload": encrypted_payload,
            "key_hint": key_hint,
            "status": CredentialStatus.ACTIVE,
            "rotated_at": datetime.now(UTC),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def rotate(self, *, encrypted_payload: str, key_hint: str = "") -> None:
        require(len(encrypted_payload) > 0, "encrypted_payload is required")
        self.encrypted_payload = encrypted_payload
        self.key_hint = key_hint.strip()[:32]
        self.status = CredentialStatus.ROTATED
        self.rotated_at = datetime.now(UTC)
        self.touch()

    def revoke(self) -> None:
        self.status = CredentialStatus.REVOKED
        self.touch()

    def to_dict(self) -> dict[str, object]:
        """Serialize without exposing ciphertext."""
        base = super().to_dict()
        base.update(
            {
                "broker_account_id": str(self.broker_account_id),
                "credential_type": self.credential_type.value,
                "key_hint": self.key_hint,
                "status": self.status.value,
                "has_secret": True,
                "rotated_at": (
                    self.rotated_at.isoformat() if self.rotated_at else None
                ),
            }
        )
        return base


@dataclass(eq=False, kw_only=True)
class BrokerConnection(Entity):
    """Connection lifecycle record for a broker account.

    Tracks adapter session state only. Does not open sockets or place orders.
    """

    broker_account_id: UUID
    status: BrokerConnectionStatus = BrokerConnectionStatus.DISCONNECTED
    last_connected_at: datetime | None = None
    last_error: str = ""
    adapter_session_ref: str = ""

    def __post_init__(self) -> None:
        self.last_error = self.last_error.strip()[:1000]
        self.adapter_session_ref = self.adapter_session_ref.strip()[:256]

    @classmethod
    def create_for_account(
        cls,
        *,
        broker_account_id: UUID,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "broker_account_id": broker_account_id,
            "status": BrokerConnectionStatus.DISCONNECTED,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def mark_connecting(self) -> None:
        self.status = BrokerConnectionStatus.CONNECTING
        self.last_error = ""
        self.touch()

    def mark_connected(self, *, adapter_session_ref: str = "") -> None:
        self.status = BrokerConnectionStatus.CONNECTED
        self.last_connected_at = datetime.now(UTC)
        self.adapter_session_ref = adapter_session_ref.strip()[:256]
        self.last_error = ""
        self.touch()

    def mark_disconnected(self) -> None:
        self.status = BrokerConnectionStatus.DISCONNECTED
        self.adapter_session_ref = ""
        self.touch()

    def mark_error(self, message: str) -> None:
        self.status = BrokerConnectionStatus.ERROR
        self.last_error = message.strip()[:1000]
        self.adapter_session_ref = ""
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "broker_account_id": str(self.broker_account_id),
                "status": self.status.value,
                "last_connected_at": (
                    self.last_connected_at.isoformat()
                    if self.last_connected_at
                    else None
                ),
                "last_error": self.last_error,
                "adapter_session_ref": self.adapter_session_ref,
            }
        )
        return base


@dataclass(eq=False, kw_only=True)
class BrokerSession(Entity):
    """Adapter session record for a connected broker account.

    Foundation stores session metadata only. No live MT5/trading socket.
    """

    broker_account_id: UUID
    connection_id: UUID
    session_ref: str
    status: BrokerConnectionStatus = BrokerConnectionStatus.CONNECTED
    expires_at: datetime | None = None
    last_refreshed_at: datetime | None = None

    def __post_init__(self) -> None:
        self.session_ref = self.session_ref.strip()[:256]
        require(len(self.session_ref) > 0, "session_ref is required")

    @classmethod
    def open(
        cls,
        *,
        broker_account_id: UUID,
        connection_id: UUID,
        session_ref: str,
        expires_at: datetime | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "broker_account_id": broker_account_id,
            "connection_id": connection_id,
            "session_ref": session_ref,
            "status": BrokerConnectionStatus.CONNECTED,
            "expires_at": expires_at,
            "last_refreshed_at": datetime.now(UTC),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def refresh(self, *, session_ref: str | None = None) -> None:
        require_state(
            self.status == BrokerConnectionStatus.CONNECTED,
            "Only connected sessions can be refreshed",
            status=self.status.value,
        )
        if session_ref is not None:
            self.session_ref = session_ref.strip()[:256]
        self.last_refreshed_at = datetime.now(UTC)
        self.touch()

    def close(self) -> None:
        self.status = BrokerConnectionStatus.DISCONNECTED
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "broker_account_id": str(self.broker_account_id),
                "connection_id": str(self.connection_id),
                "session_ref": self.session_ref,
                "status": self.status.value,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
                "last_refreshed_at": (
                    self.last_refreshed_at.isoformat()
                    if self.last_refreshed_at
                    else None
                ),
            }
        )
        return base
