"""GetVersionUseCase — expose application identity metadata.

Why this use case exists
------------------------
Clients and operators need a stable way to discover the running build.
This use case reads AppInfoPort and returns a VersionInfo DTO — no
framework or settings module coupling inside the use case itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.version import VersionInfo
from app.domain.interfaces.app_info import AppInfoPort


@dataclass(frozen=True, slots=True)
class GetVersionUseCase:
    """Return application name, version, and environment."""

    app_info: AppInfoPort

    def execute(self) -> VersionInfo:
        """Build a version DTO from the injected app-info port."""
        return VersionInfo(
            name=self.app_info.app_name,
            version=self.app_info.app_version,
            environment=self.app_info.environment,
            api_prefix=self.app_info.api_prefix,
        )
