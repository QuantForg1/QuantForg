"""Always-unhealthy probe used when an optional dependency failed to start."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UnavailableHealthCheck:
    """Report a named dependency as unavailable without raising."""

    name: str

    async def check(self) -> bool:
        return False
