"""QCS models — institutional certification quality gate (never mutates production)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "modifies_strategies": False,
    "modifies_risk": False,
    "modifies_safety": False,
    "approves_releases_automatically": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "certification_read_only": True,
    "human_approval_required_for_certification": True,
}


class CertificationLevel(StrEnum):
    NOT_READY = "Not Ready"
    DEVELOPMENT_READY = "Development Ready"
    RESEARCH_READY = "Research Ready"
    PAPER_TRADING_READY = "Paper Trading Ready"
    STAGING_READY = "Staging Ready"
    PRODUCTION_READY = "Production Ready"
    INSTITUTIONAL_CERTIFIED = "Institutional Certified"


CERTIFICATION_LEVELS: tuple[str, ...] = tuple(s.value for s in CertificationLevel)

CERTIFICATION_DOMAINS: tuple[str, ...] = (
    "Architecture",
    "Testing",
    "Replay",
    "Simulation",
    "Validation",
    "Experimentation",
    "Risk",
    "Execution",
    "Reliability",
    "Release Governance",
    "Security",
    "Performance",
    "Documentation",
    "Operational Readiness",
)

SCORE_KEYS: tuple[str, ...] = (
    "architecture_score",
    "quality_score",
    "research_score",
    "validation_score",
    "risk_score",
    "execution_score",
    "reliability_score",
    "security_score",
    "performance_score",
    "documentation_score",
    "overall_institutional_readiness_score",
)

DATA_SOURCES: tuple[str, ...] = (
    "irl",
    "replay",
    "benchmark",
    "ise",
    "cvf",
    "iep",
    "islm",
    "irap",
    "eqs",
    "res",
    "irdp",
    "icp",
    "idw",
    "aqs",
    "aqc",
    "qkg",
)
