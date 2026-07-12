"""Health-check application service.

Thin façade over :class:`GetHealthUseCase` retained for presentation-layer
compatibility. Prefer injecting the use case directly in new code.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.health import HealthReport
from app.application.use_cases.get_health import GetHealthUseCase


@dataclass(frozen=True, slots=True)
class HealthService:
    """Delegates readiness checks to :class:`GetHealthUseCase`."""

    use_case: GetHealthUseCase

    async def check(self) -> HealthReport:
        """Return the aggregated health report."""
        return await self.use_case.execute()
