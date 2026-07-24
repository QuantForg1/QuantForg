"""AOC models — autonomous operations center (never mutates production)."""

from __future__ import annotations

from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "modifies_strategies": False,
    "modifies_risk": False,
    "modifies_safety": False,
    "approves_releases": False,
    "allocates_capital": False,
    "deploys_strategies": False,
    "performs_automatic_remediation": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "operations_orchestration_read_only": True,
    "human_approval_required_for_recommendations": True,
    "preserves_existing_safety_guarantees": True,
}

RECOMMENDATION_KINDS: tuple[str, ...] = (
    "Research candidate",
    "Replay recommended",
    "Simulation recommended",
    "Validation required",
    "Risk review required",
    "Certification required",
    "Release candidate",
    "Documentation update required",
)

EXECUTIVE_SCORE_KEYS: tuple[str, ...] = (
    "platform_readiness",
    "research_readiness",
    "release_readiness",
    "portfolio_readiness",
    "operational_readiness",
)

QUEUE_PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3")

DATA_SOURCES: tuple[str, ...] = (
    "icp",
    "qcs",
    "qpm",
    "irap",
    "islm",
    "iep",
    "ise",
    "cvf",
    "eqs",
    "res",
    "aqs",
    "aqc",
    "qkg",
)
