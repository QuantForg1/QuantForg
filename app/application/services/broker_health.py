"""Connection health monitor and automatic reconnect manager (Sprint 2).

No live broker sockets — these services manage domain health state and
reconnect scheduling only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.domain.entities.broker_health import (
    BrokerConnectionHealth,
    ReconnectPolicy,
    ReconnectState,
)
from app.domain.events.broker import (
    BrokerConnectionLost,
    BrokerHealthChanged,
    BrokerHeartbeatReceived,
    BrokerReconnected,
)


@dataclass
class ConnectionHealthMonitor:
    """Tracks latency, heartbeats, uptime, and reconnect counts."""

    _by_connection: dict[UUID, BrokerConnectionHealth] = field(default_factory=dict)

    def ensure(
        self,
        *,
        connection_id: UUID,
        broker_account_id: UUID,
        broker_id: UUID,
    ) -> BrokerConnectionHealth:
        existing = self._by_connection.get(connection_id)
        if existing is not None:
            return existing
        health = BrokerConnectionHealth.create(
            connection_id=connection_id,
            broker_account_id=broker_account_id,
            broker_id=broker_id,
        )
        self._by_connection[connection_id] = health
        return health

    def get(self, connection_id: UUID) -> BrokerConnectionHealth | None:
        return self._by_connection.get(connection_id)

    def list_for_broker(self, broker_id: UUID) -> list[BrokerConnectionHealth]:
        return [h for h in self._by_connection.values() if h.broker_id == broker_id]

    def heartbeat(
        self, connection_id: UUID, *, latency_ms: float
    ) -> tuple[BrokerConnectionHealth, BrokerHeartbeatReceived]:
        health = self._require(connection_id)
        previous = health.status
        health.record_heartbeat(latency_ms=latency_ms)
        event = BrokerHeartbeatReceived(
            broker_id=health.broker_id,
            connection_id=connection_id,
            latency_ms=latency_ms,
            previous_status=previous.value,
            status=health.status.value,
        )
        return health, event

    def mark_connected(
        self, connection_id: UUID
    ) -> tuple[BrokerConnectionHealth, BrokerHealthChanged | None]:
        health = self._require(connection_id)
        previous = health.status
        health.record_successful_connection()
        changed = None
        if previous != health.status:
            changed = BrokerHealthChanged(
                broker_id=health.broker_id,
                connection_id=connection_id,
                previous_status=previous.value,
                status=health.status.value,
            )
        return health, changed

    def mark_lost(
        self, connection_id: UUID, *, error: str = ""
    ) -> tuple[BrokerConnectionHealth, BrokerConnectionLost]:
        health = self._require(connection_id)
        previous = health.status
        health.record_connection_lost(error=error)
        event = BrokerConnectionLost(
            broker_id=health.broker_id,
            connection_id=connection_id,
            previous_status=previous.value,
            status=health.status.value,
            error=health.last_error,
        )
        return health, event

    def snapshot(self, connection_id: UUID) -> dict[str, object]:
        health = self._require(connection_id)
        return health.to_dict()

    def _require(self, connection_id: UUID) -> BrokerConnectionHealth:
        health = self._by_connection.get(connection_id)
        if health is None:
            msg = f"No health record for connection {connection_id}"
            raise KeyError(msg)
        return health


@dataclass
class AutomaticReconnectManager:
    """Schedules reconnect attempts with exponential backoff and cooldown."""

    policy: ReconnectPolicy = field(default_factory=ReconnectPolicy)
    _states: dict[UUID, ReconnectState] = field(default_factory=dict)

    def state_for(self, connection_id: UUID) -> ReconnectState:
        if connection_id not in self._states:
            self._states[connection_id] = ReconnectState(connection_id=connection_id)
        return self._states[connection_id]

    def can_attempt(self, connection_id: UUID, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        state = self.state_for(connection_id)
        if state.in_cooldown(now=current):
            return False
        return not self.policy.is_exhausted(state.attempts)

    def next_delay_seconds(self, connection_id: UUID) -> float | None:
        state = self.state_for(connection_id)
        if self.policy.is_exhausted(state.attempts):
            return None
        return self.policy.delay_for_attempt(state.attempts + 1)

    def record_attempt(
        self, connection_id: UUID, *, now: datetime | None = None
    ) -> ReconnectState:
        current = now or datetime.now(UTC)
        state = self.state_for(connection_id)
        state.attempts += 1
        state.last_attempt_at = current
        state.events.append(f"attempt:{state.attempts}@{current.isoformat()}")
        if self.policy.is_exhausted(state.attempts):
            state.cooldown_until = current + timedelta(
                seconds=self.policy.cooldown_seconds
            )
            state.events.append(f"cooldown_until:{state.cooldown_until.isoformat()}")
        return state

    def record_success(
        self, connection_id: UUID, *, broker_id: UUID
    ) -> tuple[ReconnectState, BrokerReconnected]:
        state = self.state_for(connection_id)
        prior_attempts = state.attempts
        state.attempts = 0
        state.cooldown_until = None
        state.events.append("reconnected")
        event = BrokerReconnected(
            broker_id=broker_id,
            connection_id=connection_id,
            attempts=prior_attempts,
        )
        return state, event

    def reset_cooldown(self, connection_id: UUID) -> None:
        state = self.state_for(connection_id)
        state.cooldown_until = None
        state.attempts = 0
