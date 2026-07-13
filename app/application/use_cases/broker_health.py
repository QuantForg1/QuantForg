"""Broker health and diagnostics use cases (Sprint 2)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.broker import BrokerDiagnosticsDTO, BrokerHealthDTO
from app.application.services.broker_health import (
    AutomaticReconnectManager,
    ConnectionHealthMonitor,
)
from app.domain.entities.broker import Broker
from app.domain.entities.broker_health import BrokerConnectionHealth
from app.domain.entities.broker_integration import BrokerCapability
from app.domain.enums.broker import BrokerHealthStatus
from app.domain.exceptions.base import NotFoundError
from app.domain.interfaces.broker_capability_discovery import (
    default_capabilities_for_platform,
    discover_adapter_capabilities,
)
from app.domain.interfaces.broker_registry import BrokerRegistryPort
from app.domain.interfaces.broker_uow import BrokerUnitOfWorkFactory


def _worst_status(statuses: list[BrokerHealthStatus]) -> BrokerHealthStatus:
    if not statuses:
        return BrokerHealthStatus.UNKNOWN
    order = {
        BrokerHealthStatus.UNHEALTHY: 3,
        BrokerHealthStatus.DEGRADED: 2,
        BrokerHealthStatus.UNKNOWN: 1,
        BrokerHealthStatus.HEALTHY: 0,
    }
    return max(statuses, key=lambda s: order[s])


def _aggregate_health(
    *,
    broker_id: UUID,
    records: list[BrokerConnectionHealth],
    caps: list[BrokerCapability],
) -> BrokerHealthDTO:
    statuses = [r.status for r in records]
    latencies = [r.latency_ms for r in records if r.latency_ms is not None]
    reconnect = sum(r.reconnect_attempts for r in records)
    uptimes = [r.uptime_seconds for r in records]
    errors = [r.last_error for r in records if r.last_error]
    heartbeats = [r.last_heartbeat_at for r in records if r.last_heartbeat_at]
    successes = [
        r.last_successful_connection_at
        for r in records
        if r.last_successful_connection_at
    ]

    return BrokerHealthDTO(
        broker_id=broker_id,
        status=_worst_status(statuses).value,
        latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
        uptime_seconds=max(uptimes) if uptimes else 0.0,
        reconnect_count=reconnect,
        last_error=errors[-1] if errors else "",
        capabilities=tuple(c.code.value for c in caps if c.enabled),
        last_heartbeat_at=max(heartbeats) if heartbeats else None,
        last_successful_connection_at=max(successes) if successes else None,
        connection_count=len(records),
    )


async def _tenant_health_records(
    *,
    uow_factory: BrokerUnitOfWorkFactory,
    health_monitor: ConnectionHealthMonitor,
    broker_id: UUID,
    user_id: UUID | None,
) -> tuple[Broker, list[BrokerCapability], list[BrokerConnectionHealth]]:
    """Load broker health rows; when ``user_id`` is set, scope to that tenant."""
    async with uow_factory() as uow:
        broker = await uow.brokers.get_by_id(broker_id)
        if broker is None:
            raise NotFoundError(
                "Broker not found",
                details={"broker_id": str(broker_id)},
            )
        caps = await uow.capabilities.list_for_broker(broker_id)
        persisted = await uow.health.list_for_broker(broker_id)
        allowed_account_ids: set[UUID] | None = None
        if user_id is not None:
            accounts = await uow.accounts.list_for_user(user_id)
            allowed_account_ids = {a.id for a in accounts if a.broker_id == broker_id}

    live = health_monitor.list_for_broker(broker_id)
    by_connection = {h.connection_id: h for h in persisted}
    for item in live:
        by_connection[item.connection_id] = item
    records = list(by_connection.values())
    if allowed_account_ids is not None:
        records = [r for r in records if r.broker_account_id in allowed_account_ids]
    return broker, caps, records


@dataclass(frozen=True, slots=True)
class GetBrokerHealthUseCase:
    uow_factory: BrokerUnitOfWorkFactory
    health_monitor: ConnectionHealthMonitor

    async def execute(
        self, *, broker_id: UUID, user_id: UUID | None = None
    ) -> BrokerHealthDTO:
        _broker, caps, records = await _tenant_health_records(
            uow_factory=self.uow_factory,
            health_monitor=self.health_monitor,
            broker_id=broker_id,
            user_id=user_id,
        )
        return _aggregate_health(broker_id=broker_id, records=records, caps=caps)


@dataclass(frozen=True, slots=True)
class GetBrokerDiagnosticsUseCase:
    uow_factory: BrokerUnitOfWorkFactory
    health_monitor: ConnectionHealthMonitor
    reconnect_manager: AutomaticReconnectManager
    registry: BrokerRegistryPort

    async def execute(
        self, *, broker_id: UUID, user_id: UUID | None = None
    ) -> BrokerDiagnosticsDTO:
        """Diagnostics for a broker. ``user_id=None`` returns all (admin)."""
        broker, caps, records = await _tenant_health_records(
            uow_factory=self.uow_factory,
            health_monitor=self.health_monitor,
            broker_id=broker_id,
            user_id=user_id,
        )
        health = _aggregate_health(broker_id=broker_id, records=records, caps=caps)

        connection_snapshots = tuple(h.to_dict() for h in records)
        reconnect_snapshots: list[dict[str, object]] = []
        for item in records:
            connection_id = item.connection_id
            state = self.reconnect_manager.state_for(connection_id)
            reconnect_snapshots.append(
                {
                    "connection_id": str(connection_id),
                    "attempts": state.attempts,
                    "cooldown_until": (
                        state.cooldown_until.isoformat()
                        if state.cooldown_until
                        else None
                    ),
                    "last_attempt_at": (
                        state.last_attempt_at.isoformat()
                        if state.last_attempt_at
                        else None
                    ),
                    "events": list(state.events[-10:]),
                    "can_attempt": self.reconnect_manager.can_attempt(connection_id),
                    "next_delay_seconds": self.reconnect_manager.next_delay_seconds(
                        connection_id
                    ),
                }
            )

        adapter = self.registry.get(broker.platform_code.value)
        if adapter is not None:
            discovered = tuple(c.value for c in discover_adapter_capabilities(adapter))
        else:
            discovered = tuple(
                c.value
                for c in default_capabilities_for_platform(broker.platform_code.value)
            )

        return BrokerDiagnosticsDTO(
            broker_id=health.broker_id,
            status=health.status,
            latency_ms=health.latency_ms,
            uptime_seconds=health.uptime_seconds,
            reconnect_count=health.reconnect_count,
            last_error=health.last_error,
            capabilities=health.capabilities,
            discovered_capabilities=discovered,
            connections=connection_snapshots,
            reconnect=tuple(reconnect_snapshots),
            platform_code=broker.platform_code.value,
            last_heartbeat_at=health.last_heartbeat_at,
            last_successful_connection_at=health.last_successful_connection_at,
        )
