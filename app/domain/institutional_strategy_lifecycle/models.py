"""ISLM models — strategy lifecycle governance (read-only toward production)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "changes_strategy_parameters": False,
    "approves_promotions_automatically": False,
    "retires_strategies_automatically": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "lifecycle_governance_read_only": True,
    "human_approval_required_for_transitions": True,
}


class LifecycleState(StrEnum):
    DRAFT = "Draft"
    RESEARCH = "Research"
    REPLAY_VALIDATION = "Replay Validation"
    SIMULATION_VALIDATION = "Simulation Validation"
    CONTINUOUS_VALIDATION = "Continuous Validation"
    RISK_REVIEW = "Risk Review"
    RELEASE_APPROVAL = "Release Approval"
    PRODUCTION = "Production"
    MONITORING = "Monitoring"
    SUSPENDED = "Suspended"
    RETIRED = "Retired"


LIFECYCLE_ORDER: tuple[str, ...] = tuple(s.value for s in LifecycleState)
