"""Institutional Simulation Engine (ISE) — QuantForg digital twin.

Completely isolated simulation laboratory. Reproduces Market → Signal → MTF →
Quality → Confluence → Risk → Safety → OMS → Gateway → Execution using
historical baselines without touching production.
"""

from __future__ import annotations

from app.domain.institutional_simulation_engine.platform import (
    InstitutionalSimulationEngine,
)

__all__ = ["InstitutionalSimulationEngine", "get_ise"]

_ISE: InstitutionalSimulationEngine | None = None


def get_ise() -> InstitutionalSimulationEngine:
    global _ISE
    if _ISE is None:
        _ISE = InstitutionalSimulationEngine()
    return _ISE
