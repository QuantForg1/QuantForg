"""QuantForg Certification Suite (QCS) — V5 institutional quality gate.

Completely read-only. Aggregates evidence across enterprise subsystems to
compute readiness scores, certification levels and blockers.
Never executes trades or modifies production, strategies, risk or safety.
Never approves releases automatically — human approval required.
"""

from __future__ import annotations

from app.domain.quantforg_certification_suite.platform import (
    QuantForgCertificationSuite,
)

__all__ = ["QuantForgCertificationSuite", "get_qcs"]

_QCS: QuantForgCertificationSuite | None = None


def get_qcs() -> QuantForgCertificationSuite:
    global _QCS
    if _QCS is None:
        _QCS = QuantForgCertificationSuite()
    return _QCS
