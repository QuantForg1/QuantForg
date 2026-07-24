"""Institutional Experimentation Platform (IEP) — V3.4 research governance.

Completely isolated from production. Provides a governed environment to
observe, compare and archive quantitative research experiments.
Never executes trades, modifies production/strategies, or auto-approves /
auto-promotes experiments.
"""

from __future__ import annotations

from app.domain.institutional_experimentation_platform.platform import (
    InstitutionalExperimentationPlatform,
)

__all__ = ["InstitutionalExperimentationPlatform", "get_iep"]

_IEP: InstitutionalExperimentationPlatform | None = None


def get_iep() -> InstitutionalExperimentationPlatform:
    global _IEP
    if _IEP is None:
        _IEP = InstitutionalExperimentationPlatform()
    return _IEP
