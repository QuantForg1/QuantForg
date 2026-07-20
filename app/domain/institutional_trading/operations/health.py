"""Health monitoring — gateway, MT5, queues, latencies, health score."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from app.domain.institutional_trading.operations.models import HealthSnapshot


@dataclass
class HealthInputs:
    gateway_latency_ms: float = 0.0
    gateway_available: bool = True
    mt5_connected: bool = True
    cloudflare_tunnel_up: bool = True
    order_latency_ms: float = 0.0
    journal_latency_ms: float = 0.0
    research_queue_depth: int = 0
    simulation_queue_depth: int = 0
    oms_queue_depth: int = 0
    decision_throughput_per_min: float = 0.0


@dataclass
class HealthMonitor:
    _last: HealthSnapshot | None = field(default=None, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    high_latency_ms: float = 500.0

    def observe(
        self, inputs: HealthInputs, *, now: datetime | None = None
    ) -> HealthSnapshot:
        score = 100
        if not inputs.gateway_available:
            score -= 30
        if not inputs.mt5_connected:
            score -= 30
        if not inputs.cloudflare_tunnel_up:
            score -= 15
        if inputs.gateway_latency_ms > self.high_latency_ms:
            score -= 10
        if inputs.order_latency_ms > self.high_latency_ms:
            score -= 10
        if inputs.oms_queue_depth > 100:
            score -= 5
        score = max(0, min(100, score))
        snap = HealthSnapshot(
            gateway_latency_ms=inputs.gateway_latency_ms,
            gateway_available=inputs.gateway_available,
            mt5_connected=inputs.mt5_connected,
            cloudflare_tunnel_up=inputs.cloudflare_tunnel_up,
            order_latency_ms=inputs.order_latency_ms,
            journal_latency_ms=inputs.journal_latency_ms,
            research_queue_depth=inputs.research_queue_depth,
            simulation_queue_depth=inputs.simulation_queue_depth,
            oms_queue_depth=inputs.oms_queue_depth,
            decision_throughput_per_min=inputs.decision_throughput_per_min,
            health_score=score,
            checked_at=now or datetime.now(UTC),
        )
        with self._lock:
            self._last = snap
        return snap

    def latest(self) -> HealthSnapshot | None:
        with self._lock:
            return self._last
