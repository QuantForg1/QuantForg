"""Chaos testing — simulate outages; verify graceful degradation."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from app.domain.institutional_trading.reliability.health import (
    ContinuousHealthMonitor,
    ProbeInputs,
)
from app.domain.institutional_trading.reliability.models import ContinuousHealthSnapshot


@dataclass
class ChaosHarness:
    """Inject failures without touching OMS/order_send."""

    _active: set[str] = field(default_factory=set, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def inject(self, failure: str) -> None:
        allowed = {
            "gateway_offline",
            "mt5_offline",
            "tunnel_offline",
            "high_latency",
            "database_unavailable",
        }
        if failure not in allowed:
            raise ValueError(f"unsupported chaos scenario: {failure}")
        with self._lock:
            self._active.add(failure)

    def clear(self, failure: str | None = None) -> None:
        with self._lock:
            if failure is None:
                self._active.clear()
            else:
                self._active.discard(failure)

    def active(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._active))

    def apply_to_probes(self, base: ProbeInputs) -> ProbeInputs:
        active = self.active()
        gw_ok = base.gateway_available and "gateway_offline" not in active
        mt5_ok = base.mt5_connected and "mt5_offline" not in active
        tunnel_ok = base.cloudflare_tunnel_up and "tunnel_offline" not in active
        db_lat = base.database_latency_ms
        supabase = base.supabase_up
        if "database_unavailable" in active:
            db_lat = 99999.0
            supabase = False
        gw_lat = base.gateway_latency_ms
        exec_lat = base.execution_latency_ms
        if "high_latency" in active:
            gw_lat = max(gw_lat, 2000.0)
            exec_lat = max(exec_lat, 2000.0)
        return ProbeInputs(
            gateway_latency_ms=gw_lat,
            gateway_available=gw_ok,
            mt5_connected=mt5_ok,
            cloudflare_tunnel_up=tunnel_ok,
            railway_api_up=base.railway_api_up,
            supabase_up=supabase,
            database_latency_ms=db_lat,
            oms_latency_ms=base.oms_latency_ms,
            execution_latency_ms=exec_lat,
            decision_latency_ms=base.decision_latency_ms,
            pme_latency_ms=base.pme_latency_ms,
            chaos_active=active,
        )

    def verify_degradation(
        self,
        monitor: ContinuousHealthMonitor,
        base: ProbeInputs,
    ) -> ContinuousHealthSnapshot:
        """Run observe under chaos; expect degraded=True when failures active."""
        probed = self.apply_to_probes(base)
        snap = monitor.observe(probed)
        return snap
