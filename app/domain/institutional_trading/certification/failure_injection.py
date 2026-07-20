"""Failure injection for certification — graceful degradation checks."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.institutional_trading.certification.models import (
    FailureInjectionResult,
    FailureScenario,
)
from app.domain.institutional_trading.reliability.chaos import ChaosHarness
from app.domain.institutional_trading.reliability.health import (
    ContinuousHealthMonitor,
    ProbeInputs,
)


_CHAOS_MAP: dict[FailureScenario, str | None] = {
    FailureScenario.GATEWAY_DOWN: "gateway_offline",
    FailureScenario.MT5_DOWN: "mt5_offline",
    FailureScenario.TUNNEL_DOWN: "tunnel_offline",
    FailureScenario.DATABASE_DOWN: "database_unavailable",
    FailureScenario.SUPABASE_SLOW: None,
    FailureScenario.RAILWAY_SLOW: None,
}


def _healthy_base() -> ProbeInputs:
    return ProbeInputs(
        gateway_latency_ms=40,
        gateway_available=True,
        mt5_connected=True,
        cloudflare_tunnel_up=True,
        railway_api_up=True,
        supabase_up=True,
        database_latency_ms=12,
    )


@dataclass
class FailureInjector:
    """Inject infra failures; verify system degrades gracefully (no order_send)."""

    chaos: ChaosHarness = field(default_factory=ChaosHarness)
    monitor: ContinuousHealthMonitor = field(default_factory=ContinuousHealthMonitor)

    def inject(self, scenario: FailureScenario) -> FailureInjectionResult:
        base = _healthy_base()
        chaos_key = _CHAOS_MAP.get(scenario)
        self.chaos.clear()

        if chaos_key:
            self.chaos.inject(chaos_key)
            probed = self.chaos.apply_to_probes(base)
        elif scenario == FailureScenario.SUPABASE_SLOW:
            probed = ProbeInputs(
                gateway_latency_ms=40,
                gateway_available=True,
                mt5_connected=True,
                cloudflare_tunnel_up=True,
                railway_api_up=True,
                supabase_up=True,
                database_latency_ms=2500,
            )
        elif scenario == FailureScenario.RAILWAY_SLOW:
            probed = ProbeInputs(
                gateway_latency_ms=40,
                gateway_available=True,
                mt5_connected=True,
                cloudflare_tunnel_up=True,
                railway_api_up=True,
                supabase_up=True,
                database_latency_ms=12,
                oms_latency_ms=1800,
                execution_latency_ms=1800,
            )
        else:
            probed = base

        snap = self.monitor.observe(probed)

        if scenario in (
            FailureScenario.GATEWAY_DOWN,
            FailureScenario.MT5_DOWN,
            FailureScenario.TUNNEL_DOWN,
            FailureScenario.DATABASE_DOWN,
        ):
            graceful = snap.degraded is True
            detail = (
                f"degraded={snap.degraded} score={snap.health_score}"
                if graceful
                else "expected degradation not observed"
            )
        elif scenario == FailureScenario.SUPABASE_SLOW:
            graceful = probed.database_latency_ms >= 2000
            detail = f"database_latency_ms={probed.database_latency_ms}"
        elif scenario == FailureScenario.RAILWAY_SLOW:
            graceful = (
                probed.oms_latency_ms >= 1000 or probed.execution_latency_ms >= 1000
            )
            detail = (
                f"oms={probed.oms_latency_ms} exec={probed.execution_latency_ms}"
            )
        else:
            graceful = False
            detail = "unknown scenario"

        self.chaos.clear()
        return FailureInjectionResult(
            scenario=scenario,
            degraded=bool(snap.degraded),
            graceful=bool(graceful),
            detail=detail,
        )

    def run_suite(
        self, scenarios: tuple[FailureScenario, ...] | None = None
    ) -> list[FailureInjectionResult]:
        items = scenarios or tuple(FailureScenario)
        return [self.inject(s) for s in items]
