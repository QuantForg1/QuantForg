"""Institutional Observability Platform — monitoring and diagnostics only.

Never modifies trading behaviour or any prior advisory/governance labs.
"""

from __future__ import annotations

from app.domain.institutional_observability.alerts import detect_alerts
from app.domain.institutional_observability.health import probe_components
from app.domain.institutional_observability.models import COMPONENTS, HARD_LOCKS
from app.domain.institutional_observability.reports import build_observability_pack

__all__ = [
    "COMPONENTS",
    "HARD_LOCKS",
    "build_observability_pack",
    "detect_alerts",
    "probe_components",
]
