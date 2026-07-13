"""Static / unavailable probes for optional dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.health import HealthStatus


@dataclass(frozen=True, slots=True)
class UnavailableHealthCheck:
    """Report a named dependency as unavailable without raising."""

    name: str

    async def check(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class StaticHealthCheck:
    """Report a fixed health status (e.g. redis intentionally disabled)."""

    name: str
    status: HealthStatus

    async def check(self) -> HealthStatus:
        return self.status
