"""Unit tests for connection health monitor and reconnect manager."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.services.broker_health import (
    AutomaticReconnectManager,
    ConnectionHealthMonitor,
)
from app.domain.entities.broker_health import ReconnectPolicy
from app.domain.enums.broker import BrokerHealthStatus
from app.domain.events.broker import (
    BrokerConnectionLost,
    BrokerHeartbeatReceived,
    BrokerReconnected,
)


@pytest.mark.unit
class TestConnectionHealthMonitor:
    def test_tracks_latency_heartbeat_and_uptime(self) -> None:
        monitor = ConnectionHealthMonitor()
        connection_id = uuid4()
        account_id = uuid4()
        broker_id = uuid4()
        health = monitor.ensure(
            connection_id=connection_id,
            broker_account_id=account_id,
            broker_id=broker_id,
        )
        assert health.status is BrokerHealthStatus.UNKNOWN

        monitor.mark_connected(connection_id)
        health, event = monitor.heartbeat(connection_id, latency_ms=12.5)
        assert isinstance(event, BrokerHeartbeatReceived)
        assert health.latency_ms == 12.5
        assert health.last_heartbeat_at is not None
        assert health.last_successful_connection_at is not None
        assert health.status is BrokerHealthStatus.HEALTHY
        assert health.uptime_seconds >= 0.0

    def test_connection_lost_updates_error_and_status(self) -> None:
        monitor = ConnectionHealthMonitor()
        connection_id = uuid4()
        monitor.ensure(
            connection_id=connection_id,
            broker_account_id=uuid4(),
            broker_id=uuid4(),
        )
        monitor.mark_connected(connection_id)
        health, event = monitor.mark_lost(connection_id, error="socket closed")
        assert isinstance(event, BrokerConnectionLost)
        assert health.status is BrokerHealthStatus.UNHEALTHY
        assert health.last_error == "socket closed"
        assert health.uptime_seconds == 0.0


@pytest.mark.unit
class TestAutomaticReconnectManager:
    def test_exponential_backoff_and_limits(self) -> None:
        policy = ReconnectPolicy(
            max_attempts=3,
            base_delay_seconds=1.0,
            max_delay_seconds=10.0,
            cooldown_seconds=60.0,
        )
        manager = AutomaticReconnectManager(policy=policy)
        connection_id = uuid4()

        assert manager.next_delay_seconds(connection_id) == 1.0
        manager.record_attempt(connection_id)
        assert manager.next_delay_seconds(connection_id) == 2.0
        manager.record_attempt(connection_id)
        assert manager.next_delay_seconds(connection_id) == 4.0
        manager.record_attempt(connection_id)
        assert manager.next_delay_seconds(connection_id) is None
        assert not manager.can_attempt(connection_id)

    def test_cooldown_blocks_attempts(self) -> None:
        policy = ReconnectPolicy(max_attempts=1, cooldown_seconds=300.0)
        manager = AutomaticReconnectManager(policy=policy)
        connection_id = uuid4()
        now = datetime.now(UTC)
        manager.record_attempt(connection_id, now=now)
        soon = now + timedelta(seconds=1)
        assert manager.state_for(connection_id).in_cooldown(now=soon)
        assert not manager.can_attempt(connection_id, now=soon)
        # After cooldown window expires, attempts were exhausted so still blocked
        # until reset_cooldown clears state.
        manager.reset_cooldown(connection_id)
        assert manager.can_attempt(connection_id, now=now + timedelta(seconds=301))

    def test_success_emits_reconnected_and_resets(self) -> None:
        manager = AutomaticReconnectManager(
            policy=ReconnectPolicy(max_attempts=5, base_delay_seconds=1.0)
        )
        connection_id = uuid4()
        broker_id = uuid4()
        manager.record_attempt(connection_id)
        manager.record_attempt(connection_id)
        state, event = manager.record_success(connection_id, broker_id=broker_id)
        assert isinstance(event, BrokerReconnected)
        assert event.attempts == 2
        assert state.attempts == 0
        assert state.cooldown_until is None
        assert manager.can_attempt(connection_id)
