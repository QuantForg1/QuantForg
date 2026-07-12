"""Application identity metadata port.

Allows use cases to read deployment identity (name, version, environment)
without depending on concrete settings or infrastructure modules.
"""

from __future__ import annotations

from typing import Protocol


class AppInfoPort(Protocol):
    """Read-only application metadata for health and version use cases."""

    @property
    def app_name(self) -> str:
        """Human-readable application name."""
        ...

    @property
    def app_version(self) -> str:
        """Semantic version string."""
        ...

    @property
    def environment(self) -> str:
        """Runtime environment name (development, production, …)."""
        ...

    @property
    def api_prefix(self) -> str:
        """HTTP API route prefix."""
        ...

    @property
    def health_check_timeout_seconds(self) -> float:
        """Per-probe timeout for readiness checks."""
        ...
