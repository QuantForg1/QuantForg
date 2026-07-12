"""Health-check DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class HealthStatus(StrEnum):
    """Overall or per-dependency health state."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class DependencyStatus:
    """Health status of a single infrastructure dependency."""

    name: str
    status: HealthStatus
    latency_ms: float


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Aggregated health report returned by :class:`HealthService`."""

    status: HealthStatus
    version: str
    environment: str
    dependencies: list[DependencyStatus] = field(default_factory=list)
