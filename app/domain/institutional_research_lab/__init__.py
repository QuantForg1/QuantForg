"""Institutional Research Lab (IRL) — completely isolated from production trading.

Never executes live trades. Never writes production tables. Never mutates
Strategy / Risk / Safety / OMS / Gateway / Auto Trading / live thresholds.
"""

from __future__ import annotations

from app.domain.institutional_research_lab.models import (
    ExperimentStatus,
    ReplayWindow,
    ResearchVerdict,
)
from app.domain.institutional_research_lab.platform import InstitutionalResearchLab

__all__ = [
    "ExperimentStatus",
    "InstitutionalResearchLab",
    "ReplayWindow",
    "ResearchVerdict",
    "get_irl",
]

_LAB: InstitutionalResearchLab | None = None


def get_irl() -> InstitutionalResearchLab:
    global _LAB
    if _LAB is None:
        _LAB = InstitutionalResearchLab()
    return _LAB
