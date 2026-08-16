"""Phase C research integrity & model governance — RESEARCH/SHADOW only.

Naming note: Execution Bridge docs historically used \"Phase C\" for OMS
bridging. This package is the research-integrity Phase C. It never submits
or modifies production orders.

Progression: RESEARCH → VALIDATION → SHADOW → EVIDENCE → PROMOTION REVIEW
→ ONLY THEN possible LIVE change (never automatic in Phase C).
"""

from __future__ import annotations

from app.domain.institutional_trading.phase_c.plane import (
    PhaseCControlPlane,
    get_phase_c_plane,
    reset_phase_c_plane_for_tests,
)

__all__ = [
    "PhaseCControlPlane",
    "get_phase_c_plane",
    "reset_phase_c_plane_for_tests",
]
