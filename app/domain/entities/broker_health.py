"""Connection health and reconnect domain models (Sprint 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.broker import BrokerHealthStatus


@dataclass(eq=False, kw_only=True)
class BrokerConnectionHealth(Entity):
    """Persisted health metrics for a broker connection."""

    connection_id: UUID
    broker_account_id: UUID
    broker_id: UUID
    status: BrokerHealthStatus = BrokerHealthStatus.UNKNOWN
    latency_ms: float | None = None
    last_heartbeat_at: datetime | None = None
    last_successful_connection_at: datetime | None = None
    reconnect_attempts: int = 0
    connected_since: datetime | None = None
    last_error: str = ""
    uptime_seconds: float = 0.0

    def __post_init__(self) -> None:
        require(self.reconnect_attempts >= 0, "reconnect_attempts must be >= 0")
        self.last_error = self.last_error.strip()[:1000]

    @classmethod
    def create(
        cls,
        *,
        connection_id: UUID,
        broker_account_id: UUID,
        broker_id: UUID,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "connection_id": connection_id,
            "broker_account_id": broker_account_id,
            "broker_id": broker_id,
            "status": BrokerHealthStatus.UNKNOWN,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def record_heartbeat(self, *, latency_ms: float) -> None:
        now = datetime.now(UTC)
        self.last_heartbeat_at = now
        self.latency_ms = max(0.0, latency_ms)
        if self.connected_since is None:
            self.connected_since = now
        self.uptime_seconds = (now - self.connected_since).total_seconds()
        self.status = BrokerHealthStatus.HEALTHY
        self.last_error = ""
        self.touch()

    def record_successful_connection(self) -> None:
        now = datetime.now(UTC)
        self.last_successful_connection_at = now
        self.connected_since = now
        self.reconnect_attempts = 0
        self.status = BrokerHealthStatus.HEALTHY
        self.last_error = ""
        self.uptime_seconds = 0.0
        self.touch()

    def record_connection_lost(self, *, error: str = "") -> None:
        self.status = BrokerHealthStatus.UNHEALTHY
        self.last_error = error.strip()[:1000]
        self.connected_since = None
        self.uptime_seconds = 0.0
        self.touch()

    def record_reconnect_attempt(self) -> None:
        self.reconnect_attempts += 1
        self.status = BrokerHealthStatus.DEGRADED
        self.touch()

    def mark_degraded(self, *, error: str = "") -> None:
        self.status = BrokerHealthStatus.DEGRADED
        if error:
            self.last_error = error.strip()[:1000]
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "connection_id": str(self.connection_id),
                "broker_account_id": str(self.broker_account_id),
                "broker_id": str(self.broker_id),
                "status": self.status.value,
                "latency_ms": self.latency_ms,
                "last_heartbeat_at": (
                    self.last_heartbeat_at.isoformat()
                    if self.last_heartbeat_at
                    else None
                ),
                "last_successful_connection_at": (
                    self.last_successful_connection_at.isoformat()
                    if self.last_successful_connection_at
                    else None
                ),
                "reconnect_attempts": self.reconnect_attempts,
                "connected_since": (
                    self.connected_since.isoformat() if self.connected_since else None
                ),
                "last_error": self.last_error,
                "uptime_seconds": self.uptime_seconds,
            }
        )
        return base


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    """Exponential backoff reconnect policy."""

    max_attempts: int = 5
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    cooldown_seconds: float = 300.0

    def delay_for_attempt(self, attempt: int) -> float:
        """Return backoff delay for 1-based attempt number."""
        if attempt < 1:
            return self.base_delay_seconds
        delay = self.base_delay_seconds * (2 ** (attempt - 1))
        return float(min(delay, self.max_delay_seconds))

    def is_exhausted(self, attempts: int) -> bool:
        return attempts >= self.max_attempts


@dataclass
class ReconnectState:
    """In-memory reconnect bookkeeping for a connection."""

    connection_id: UUID
    attempts: int = 0
    last_attempt_at: datetime | None = None
    cooldown_until: datetime | None = None
    events: list[str] = field(default_factory=list)

    def in_cooldown(self, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        return self.cooldown_until is not None and current < self.cooldown_until
