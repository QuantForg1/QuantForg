"""Continuous health monitoring — all production dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from app.domain.institutional_trading.reliability.models import ContinuousHealthSnapshot


@dataclass
class ProbeInputs:
    gateway_latency_ms: float = 0.0
    gateway_available: bool = True
    mt5_connected: bool = True
    cloudflare_tunnel_up: bool = True
    railway_api_up: bool = True
    supabase_up: bool = True
    database_latency_ms: float = 0.0
    oms_latency_ms: float = 0.0
    execution_latency_ms: float = 0.0
    decision_latency_ms: float = 0.0
    pme_latency_ms: float = 0.0
    chaos_active: tuple[str, ...] = ()


@dataclass
class ContinuousHealthMonitor:
    high_latency_ms: float = 500.0
    _history: list[ContinuousHealthSnapshot] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)
    max_history: int = 2000

    def observe(
        self, inputs: ProbeInputs, *, now: datetime | None = None
    ) -> ContinuousHealthSnapshot:
        score = 100
        if not inputs.gateway_available:
            score -= 20
        if not inputs.mt5_connected:
            score -= 20
        if not inputs.cloudflare_tunnel_up:
            score -= 10
        if not inputs.railway_api_up:
            score -= 10
        if not inputs.supabase_up:
            score -= 10
        for lat in (
            inputs.gateway_latency_ms,
            inputs.database_latency_ms,
            inputs.oms_latency_ms,
            inputs.execution_latency_ms,
            inputs.decision_latency_ms,
            inputs.pme_latency_ms,
        ):
            if lat > self.high_latency_ms:
                score -= 5
        score = max(0, min(100, score))
        degraded = score < 70 or bool(inputs.chaos_active)
        snap = ContinuousHealthSnapshot(
            gateway_latency_ms=inputs.gateway_latency_ms,
            gateway_available=inputs.gateway_available,
            mt5_connected=inputs.mt5_connected,
            cloudflare_tunnel_up=inputs.cloudflare_tunnel_up,
            railway_api_up=inputs.railway_api_up,
            supabase_up=inputs.supabase_up,
            database_latency_ms=inputs.database_latency_ms,
            oms_latency_ms=inputs.oms_latency_ms,
            execution_latency_ms=inputs.execution_latency_ms,
            decision_latency_ms=inputs.decision_latency_ms,
            pme_latency_ms=inputs.pme_latency_ms,
            health_score=score,
            checked_at=now or datetime.now(UTC),
            degraded=degraded,
            chaos_active=inputs.chaos_active,
        )
        with self._lock:
            self._history.append(snap)
            if len(self._history) > self.max_history:
                self._history = self._history[-self.max_history :]
        return snap

    def latest(self) -> ContinuousHealthSnapshot | None:
        with self._lock:
            return self._history[-1] if self._history else None

    def series(self, *, limit: int = 100) -> list[ContinuousHealthSnapshot]:
        with self._lock:
            return list(self._history[-limit:])
