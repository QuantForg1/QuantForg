"""Institutional Release & Deployment Platform (IRDP) — V3 release governance.

Human approval required for every release. Never executes trades, never
auto-modifies strategy/risk/safety, never auto-approves or auto-rollbacks.
Preserves all existing production safety guarantees.
"""

from __future__ import annotations

from app.domain.institutional_release_deployment.platform import (
    InstitutionalReleaseDeploymentPlatform,
)

__all__ = ["InstitutionalReleaseDeploymentPlatform", "get_irdp"]

_IRDP: InstitutionalReleaseDeploymentPlatform | None = None


def get_irdp() -> InstitutionalReleaseDeploymentPlatform:
    global _IRDP
    if _IRDP is None:
        _IRDP = InstitutionalReleaseDeploymentPlatform()
    return _IRDP
