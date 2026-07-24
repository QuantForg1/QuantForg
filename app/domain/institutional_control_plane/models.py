"""ICP models — executive operations layer (never mutates production)."""

from __future__ import annotations

from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "modifies_strategy": False,
    "modifies_risk": False,
    "modifies_releases": False,
    "approves_experiments": False,
    "approves_lifecycle_transitions": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "executive_ops_read_only": True,
}

SUBSYSTEMS: tuple[str, ...] = (
    "icc",
    "idw",
    "cvf",
    "ise",
    "iep",
    "islm",
    "irap",
    "eqs",
    "res",
    "irdp",
    "aqs",
    "aqc",
    "qkg",
)

HEALTH_SCORE_KEYS: tuple[str, ...] = (
    "overall_platform_health",
    "trading_health",
    "execution_health",
    "reliability_health",
    "validation_health",
    "research_health",
    "simulation_health",
    "experiment_health",
    "risk_health",
    "release_health",
)

ALERT_SEVERITIES: tuple[str, ...] = (
    "Critical",
    "High",
    "Medium",
    "Informational",
)

# Directed edges for dependency explorer (source → depends_on target conceptually)
DEPENDENCY_EDGES: tuple[tuple[str, str], ...] = (
    ("icc", "idw"),
    ("icc", "eqs"),
    ("icc", "res"),
    ("cvf", "eqs"),
    ("cvf", "ise"),
    ("cvf", "aqs"),
    ("ise", "qkg"),
    ("iep", "ise"),
    ("iep", "cvf"),
    ("iep", "irap"),
    ("iep", "aqs"),
    ("iep", "qkg"),
    ("islm", "iep"),
    ("islm", "cvf"),
    ("islm", "irap"),
    ("islm", "eqs"),
    ("islm", "res"),
    ("islm", "irdp"),
    ("islm", "qkg"),
    ("irap", "ise"),
    ("irap", "cvf"),
    ("irdp", "cvf"),
    ("irdp", "eqs"),
    ("irdp", "res"),
    ("irdp", "ise"),
    ("aqs", "qkg"),
    ("aqs", "ise"),
    ("aqc", "icc"),
    ("aqc", "qkg"),
    ("aqc", "res"),
    ("aqc", "eqs"),
    ("res", "eqs"),
    ("res", "icc"),
    ("eqs", "icc"),
)
