"""Version reporting application service.

Thin façade over :class:`GetVersionUseCase` retained for presentation-layer
compatibility. Prefer injecting the use case directly in new code.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.version import VersionInfo
from app.application.use_cases.get_version import GetVersionUseCase


@dataclass(frozen=True, slots=True)
class VersionService:
    """Delegates version lookups to :class:`GetVersionUseCase`."""

    use_case: GetVersionUseCase

    def get_version(self) -> VersionInfo:
        """Return application version metadata."""
        return self.use_case.execute()
