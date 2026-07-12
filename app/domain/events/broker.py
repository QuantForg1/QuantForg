"""Broker domain events — catalogue and connection lifecycle facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class BrokerRegistered(DomainEvent):
    """Emitted when a broker catalogue entry is registered."""

    event_type: ClassVar[str] = "broker.registered"
    broker_id: UUID
    slug: str
    platform_code: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "broker_id": str(self.broker_id),
                "slug": self.slug,
                "platform_code": self.platform_code,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class BrokerConnected(DomainEvent):
    """Emitted when a broker account connection reaches connected state."""

    event_type: ClassVar[str] = "broker.connected"
    broker_id: UUID
    broker_account_id: UUID
    connection_id: UUID
    session_id: UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "broker_id": str(self.broker_id),
                "broker_account_id": str(self.broker_account_id),
                "connection_id": str(self.connection_id),
                "session_id": str(self.session_id) if self.session_id else None,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class BrokerDisconnected(DomainEvent):
    """Emitted when a broker account is disconnected."""

    event_type: ClassVar[str] = "broker.disconnected"
    broker_id: UUID
    broker_account_id: UUID
    connection_id: UUID

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "broker_id": str(self.broker_id),
                "broker_account_id": str(self.broker_account_id),
                "connection_id": str(self.connection_id),
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class CredentialsUpdated(DomainEvent):
    """Emitted when broker credentials are stored or rotated."""

    event_type: ClassVar[str] = "broker.credentials_updated"
    broker_account_id: UUID
    credential_types: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "broker_account_id": str(self.broker_account_id),
                "credential_types": list(self.credential_types),
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class BrokerDeleted(DomainEvent):
    """Emitted when a broker catalogue entry is deleted."""

    event_type: ClassVar[str] = "broker.deleted"
    broker_id: UUID
    slug: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "broker_id": str(self.broker_id),
                "slug": self.slug,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class BrokerHeartbeatReceived(DomainEvent):
    event_type: ClassVar[str] = "broker.heartbeat_received"
    broker_id: UUID
    connection_id: UUID
    latency_ms: float
    previous_status: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "broker_id": str(self.broker_id),
                "connection_id": str(self.connection_id),
                "latency_ms": self.latency_ms,
                "previous_status": self.previous_status,
                "status": self.status,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class BrokerHealthChanged(DomainEvent):
    event_type: ClassVar[str] = "broker.health_changed"
    broker_id: UUID
    connection_id: UUID
    previous_status: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "broker_id": str(self.broker_id),
                "connection_id": str(self.connection_id),
                "previous_status": self.previous_status,
                "status": self.status,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class BrokerReconnected(DomainEvent):
    event_type: ClassVar[str] = "broker.reconnected"
    broker_id: UUID
    connection_id: UUID
    attempts: int

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "broker_id": str(self.broker_id),
                "connection_id": str(self.connection_id),
                "attempts": self.attempts,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class BrokerConnectionLost(DomainEvent):
    event_type: ClassVar[str] = "broker.connection_lost"
    broker_id: UUID
    connection_id: UUID
    previous_status: str
    status: str
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "broker_id": str(self.broker_id),
                "connection_id": str(self.connection_id),
                "previous_status": self.previous_status,
                "status": self.status,
                "error": self.error,
            }
        )
        return payload
