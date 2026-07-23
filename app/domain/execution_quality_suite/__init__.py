"""Execution Quality Suite (EQS) — execution intelligence layer (V2.1).

Completely read-only. Measures execution performance from signal to broker
confirmation. Never executes trades or modifies strategy, thresholds, risk,
safety, OMS, gateway, scheduler, production data, or research.
"""

from __future__ import annotations

from app.domain.execution_quality_suite.platform import ExecutionQualitySuite

__all__ = ["ExecutionQualitySuite", "get_eqs"]

_EQS: ExecutionQualitySuite | None = None


def get_eqs() -> ExecutionQualitySuite:
    global _EQS
    if _EQS is None:
        _EQS = ExecutionQualitySuite()
    return _EQS
