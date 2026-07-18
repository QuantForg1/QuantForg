"""Broker/region/health-aware gateway routing + failover."""

from __future__ import annotations

from app.domain.cloud.registry import GatewayRegistry, RouteDecision
from app.domain.cloud.types import GatewayRecord, GatewayStatus


def route_gateway(
    registry: GatewayRegistry,
    *,
    broker: str,
    region: str | None = None,
    require_capability: str | None = None,
) -> RouteDecision:
    """Pick the best online gateway; degrade gracefully when none healthy."""
    broker_code = broker.strip().lower()
    region_code = (region or "").strip().lower()
    rows = [
        g
        for g in registry.all_gateways()
        if g.broker.strip().lower() == broker_code and g.compatible
    ]
    candidates = [g.gateway_id for g in rows]

    def _cap_ok(g: GatewayRecord) -> bool:
        if not require_capability:
            return True
        caps = g.capabilities.to_dict()
        return bool(caps.get(require_capability, False))

    healthy = [g for g in rows if g.status is GatewayStatus.ONLINE and _cap_ok(g)]
    if region_code:
        regional = [g for g in healthy if g.region.strip().lower() == region_code]
        if regional:
            pick = _lowest_latency(regional)
            return RouteDecision(
                gateway_id=pick.gateway_id,
                hostname=pick.hostname,
                broker=broker_code,
                region=pick.region,
                reason="broker+region+health",
                candidates=candidates,
            )

    if healthy:
        pick = _lowest_latency(healthy)
        return RouteDecision(
            gateway_id=pick.gateway_id,
            hostname=pick.hostname,
            broker=broker_code,
            region=pick.region,
            reason="broker+health",
            candidates=candidates,
        )

    # Failover: degraded same broker
    degraded = [g for g in rows if g.status is GatewayStatus.DEGRADED and _cap_ok(g)]
    if degraded:
        pick = _lowest_latency(degraded)
        return RouteDecision(
            gateway_id=pick.gateway_id,
            hostname=pick.hostname,
            broker=broker_code,
            region=pick.region,
            reason="failover_degraded",
            fallback_used=True,
            candidates=candidates,
        )

    # Graceful degradation: any registered broker gateway (offline noted)
    if rows:
        pick = rows[0]
        return RouteDecision(
            gateway_id=pick.gateway_id,
            hostname=pick.hostname,
            broker=broker_code,
            region=pick.region,
            reason="graceful_degradation_unhealthy",
            fallback_used=True,
            candidates=candidates,
        )

    return RouteDecision(
        gateway_id=None,
        hostname=None,
        broker=broker_code,
        region=region_code or "",
        reason="no_gateway_registered",
        candidates=[],
    )


def _lowest_latency(rows: list[GatewayRecord]) -> GatewayRecord:
    def key(g: GatewayRecord) -> float:
        if g.latency_ms is None:
            return 1e9
        return float(g.latency_ms)

    return sorted(rows, key=key)[0]


def mark_stale_offline(
    registry: GatewayRegistry, *, timeout_seconds: float = 30.0
) -> list[str]:
    """Failure detection — mark gateways offline when heartbeat is stale."""
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
    changed: list[str] = []
    for g in registry.all_gateways():
        if not g.last_seen_at:
            if g.status is not GatewayStatus.OFFLINE:
                registry.record_failure(g.gateway_id, "heartbeat_timeout", "never seen")
                changed.append(g.gateway_id)
            continue
        try:
            seen = datetime.fromisoformat(g.last_seen_at)
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=UTC)
        except ValueError:
            registry.record_failure(g.gateway_id, "heartbeat_timeout", "bad timestamp")
            changed.append(g.gateway_id)
            continue
        if seen < cutoff and g.status is GatewayStatus.ONLINE:
            registry.record_failure(
                g.gateway_id, "heartbeat_timeout", f"last_seen={g.last_seen_at}"
            )
            changed.append(g.gateway_id)
    return changed
