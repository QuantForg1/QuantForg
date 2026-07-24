"""QDIE models — Decision Intelligence Engine (advisory only)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "modifies_strategies": False,
    "modifies_risk": False,
    "approves_releases": False,
    "allocates_capital": False,
    "performs_automatic_actions": False,
    "human_approval_required": True,
    "advisory_only": True,
    "writes_production_tables": False,
}


class DecisionCategory(StrEnum):
    RESEARCH = "Research Decision"
    STRATEGY = "Strategy Decision"
    VALIDATION = "Validation Decision"
    RISK = "Risk Review"
    PORTFOLIO = "Portfolio Review"
    RELEASE = "Release Review"
    OPERATIONAL = "Operational Review"


DECISION_CATEGORIES: tuple[str, ...] = tuple(c.value for c in DecisionCategory)

DATA_SOURCES: tuple[str, ...] = (
    "irl",
    "replay",
    "ise",
    "iep",
    "cvf",
    "irap",
    "eqs",
    "res",
    "qcs",
    "qpm",
    "islm",
    "irdp",
    "icp",
    "aoc",
    "qkg",
    "qem",
    "qcdm",
)

SCORE_KEYS: tuple[str, ...] = (
    "confidence",
    "evidence_quality",
    "research_quality",
    "validation_strength",
    "simulation_consistency",
    "portfolio_impact",
    "operational_readiness",
    "overall_decision_score",
)

PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3")
