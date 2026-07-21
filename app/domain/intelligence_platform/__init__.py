"""QuantForg Intelligence Platform.

Institutional research and continuous improvement environment.
Never sends broker orders. Replay never affects production.
Reports and panels use recorded data only — no fabricated metrics.
"""

from __future__ import annotations

from app.domain.intelligence_platform.config import IntelligencePlatformConfig
from app.domain.intelligence_platform.orchestrator import (
    IntelligenceFeeds,
    IntelligencePlatformCenter,
)

__all__ = [
    "IntelligenceFeeds",
    "IntelligencePlatformCenter",
    "IntelligencePlatformConfig",
]
