"""Institutional Control Plane (ICP) — V4 executive operations layer.

Completely read-only. Aggregates status across QuantForg enterprise
subsystems into health scores, alerts, timeline, dependencies and reports.
Never executes trades or modifies production, strategy, risk, releases,
experiments, or lifecycle approvals.
"""

from __future__ import annotations

from app.domain.institutional_control_plane.platform import InstitutionalControlPlane

__all__ = ["InstitutionalControlPlane", "get_icp"]

_ICP: InstitutionalControlPlane | None = None


def get_icp() -> InstitutionalControlPlane:
    global _ICP
    if _ICP is None:
        _ICP = InstitutionalControlPlane()
    return _ICP
