"""Version DTOs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VersionInfo:
    """Application identity metadata."""

    name: str
    version: str
    environment: str
    api_prefix: str
    git_commit: str = "unknown"
    deployment_id: str = "unknown"
