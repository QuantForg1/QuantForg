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
                healthy = await asyncio.wait_for(probe.check(), timeout=timeout)
            except TimeoutError:
                healthy = False
            except Exception:
                healthy = False
            latency_ms = (asyncio.get_running_loop().time() - started) * 1000.0
            return DependencyStatus(
                name=probe.name,
                status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
                latency_ms=round(latency_ms, 2),
            )

        results = await asyncio.gather(*[_run(p) for p in self.probes])
        dependencies = list(results)
        overall = (
            HealthStatus.HEALTHY
            if all(d.status == HealthStatus.HEALTHY for d in dependencies)
            else HealthStatus.UNHEALTHY
        )
        return HealthReport(
            status=overall,
            version=self.app_info.app_version,
            environment=self.app_info.environment,
            dependencies=dependencies,
        )
