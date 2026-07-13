"""Health-check port.

Abstracts infrastructure health probes so the application layer can
aggregate readiness without depending on concrete clients.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.application.dto.health import HealthStatus


class HealthCheckPort(Protocol):
    """Contract for a single dependency health probe."""

    @property
    def name(self) -> str:
        """Human-readable dependency name (e.g. ``postgres``, ``redis``)."""
        ...

    async def check(self) -> bool | HealthStatus:
        """Return ``True``/``HEALTHY``, ``False``/``UNHEALTHY``, or an explicit status.

        Explicit :class:`HealthStatus` values (e.g. ``DISABLED``) are used when a
        dependency is intentionally not provisioned.
        """
        ...
