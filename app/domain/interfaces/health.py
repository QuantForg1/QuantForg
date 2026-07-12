"""Health-check port.

Abstracts infrastructure health probes so the application layer can
aggregate readiness without depending on concrete clients.
"""

from __future__ import annotations

from typing import Protocol


class HealthCheckPort(Protocol):
    """Contract for a single dependency health probe."""

    @property
    def name(self) -> str:
        """Human-readable dependency name (e.g. ``postgres``, ``redis``)."""
        ...

    async def check(self) -> bool:
        """Return ``True`` when the dependency is reachable and healthy."""
        ...
