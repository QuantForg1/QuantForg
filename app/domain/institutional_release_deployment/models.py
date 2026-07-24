"""IRDP models — institutional release governance (human approval only)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "executes_trades": False,
    "modifies_strategies_automatically": False,
    "modifies_risk_automatically": False,
    "modifies_safety_automatically": False,
    "approves_releases_automatically": False,
    "rollbacks_automatically": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "human_approval_required": True,
    "preserves_production_safety_guarantees": True,
    "release_governance_layer": True,
}


class ReleaseStage(StrEnum):
    DEVELOPMENT = "Development"
    TESTING = "Testing"
    VALIDATION = "Validation"
    SIMULATION = "Simulation (ISE)"
    CONTINUOUS_VALIDATION = "Continuous Validation (CVF)"
    HUMAN_APPROVAL = "Human Approval"
    STAGING = "Staging"
    PRODUCTION = "Production"
    POST_RELEASE_MONITORING = "Post-Release Monitoring"


class ReleaseStatus(StrEnum):
    DRAFT = "Draft"
    IN_PROGRESS = "In Progress"
    AWAITING_APPROVAL = "Awaiting Approval"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    STAGED = "Staged"
    DEPLOYED = "Deployed"
    MONITORING = "Monitoring"
    ROLLED_BACK = "Rolled Back"
    ARCHIVED = "Archived"


PIPELINE_ORDER: tuple[str, ...] = tuple(s.value for s in ReleaseStage)

CHECKLIST_ITEMS: tuple[str, ...] = (
    "TypeScript compilation",
    "Python tests",
    "Integration tests",
    "Replay validation",
    "Simulation reports",
    "CVF status",
    "Execution Quality status",
    "Reliability status",
    "Knowledge Graph consistency",
    "Audit completeness",
    "Security checks",
    "Configuration integrity",
)
