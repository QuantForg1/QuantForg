"""GetHealthUseCase — aggregate infrastructure readiness probes.

Why this use case exists
------------------------
Operators and orchestrators need a single readiness signal. This use case
runs HealthCheckPort probes concurrently (via dependency inversion) and
returns a HealthReport DTO. It never imports concrete DB/Redis clients.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.application.dto.health import DependencyStatus, HealthReport, HealthStatus
from app.domain.interfaces.app_info import AppInfoPort
from app.domain.interfaces.health import HealthCheckPort

# Cache / optional infra — reported in the payload but do not fail readiness.
_OPTIONAL_DEPENDENCIES = frozenset({"redis"})


def _coerce_status(result: bool | HealthStatus) -> HealthStatus:
    if isinstance(result, HealthStatus):
        return result
    return HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY


@dataclass(frozen=True, slots=True)
class GetHealthUseCase:
    """Run readiness probes and return an aggregated health report."""

    app_info: AppInfoPort
    probes: tuple[HealthCheckPort, ...]

    async def execute(self) -> HealthReport:
        """Execute all probes within the configured timeout."""
        timeout = self.app_info.health_check_timeout_seconds

        async def _run(probe: HealthCheckPort) -> DependencyStatus:
            started = asyncio.get_running_loop().time()
            try:
                raw = await asyncio.wait_for(probe.check(), timeout=timeout)
                status = _coerce_status(raw)
            except TimeoutError:
                status = HealthStatus.UNHEALTHY
            except Exception:
                status = HealthStatus.UNHEALTHY
            latency_ms = (asyncio.get_running_loop().time() - started) * 1000.0
            return DependencyStatus(
                name=probe.name,
                status=status,
                latency_ms=round(latency_ms, 2),
            )

        results = await asyncio.gather(*[_run(p) for p in self.probes])
        dependencies = list(results)
        critical = [d for d in dependencies if d.name not in _OPTIONAL_DEPENDENCIES]
        # No critical probes (e.g. testing/memory mode) → process is healthy.
        # DISABLED is only valid for optional deps; treat as non-critical success.
        overall = (
            HealthStatus.HEALTHY
            if not critical or all(d.status == HealthStatus.HEALTHY for d in critical)
            else HealthStatus.UNHEALTHY
        )
        return HealthReport(
            status=overall,
            version=self.app_info.app_version,
            environment=self.app_info.environment,
            dependencies=dependencies,
        )
