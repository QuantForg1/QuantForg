"""QuantForg Decision Intelligence Engine (QDIE) — V7 advisory decisions.

Completely advisory. Aggregates subsystem evidence into explainable
recommendations. Never executes trades, modifies production/strategies/risk,
approves releases, allocates capital, or performs automatic actions.
Every recommendation requires explicit human approval.
"""

from __future__ import annotations

from app.domain.quantforg_decision_intelligence.platform import (
    QuantForgDecisionIntelligenceEngine,
)

__all__ = ["QuantForgDecisionIntelligenceEngine", "get_qdie"]

_QDIE: QuantForgDecisionIntelligenceEngine | None = None


def get_qdie() -> QuantForgDecisionIntelligenceEngine:
    global _QDIE
    if _QDIE is None:
        _QDIE = QuantForgDecisionIntelligenceEngine()
    return _QDIE
