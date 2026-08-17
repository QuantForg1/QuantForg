"""Phase D — evidence-gated alpha promotion & safe live evolution.

Naming note: ``tests/unit/test_institutional_trading_phase_d.py`` historically
covers PME. This package is the alpha-promotion Phase D.

HARD RULES:
- Never auto-promote to LIVE
- Candidates never call OMS / Gateway / MT5 / order_send
- Never weaken Phase A / B / C
- Fail closed for new risk
"""

from __future__ import annotations

from app.domain.institutional_trading.phase_d.plane import (
    PhaseDControlPlane,
    get_phase_d_plane,
    reset_phase_d_plane_for_tests,
)

__all__ = [
    "PhaseDControlPlane",
    "get_phase_d_plane",
    "reset_phase_d_plane_for_tests",
]
