"""Institutional Risk Analytics Platform (IRAP) — portfolio risk intelligence (V3.2).

Completely read-only. Provides institutional-grade portfolio and strategy risk
analytics using historical, live and simulated evidence.
Never executes trades or modifies production, strategy, risk parameters, or safety.
"""

from __future__ import annotations

from app.domain.institutional_risk_analytics.platform import InstitutionalRiskAnalytics

__all__ = ["InstitutionalRiskAnalytics", "get_irap"]

_IRAP: InstitutionalRiskAnalytics | None = None


def get_irap() -> InstitutionalRiskAnalytics:
    global _IRAP
    if _IRAP is None:
        _IRAP = InstitutionalRiskAnalytics()
    return _IRAP
