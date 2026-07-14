"""Institutional Execution Engine — observable pipeline stages."""

from __future__ import annotations

from enum import StrEnum

from app.domain.execution_intelligence.lifecycle import LifecycleState


class PipelineStage(StrEnum):
    """Every order advances through these stages when the engine runs."""

    DRAFT = "Draft"
    VALIDATION = "Validation"
    RISK_CHECK = "Risk Check"
    EXECUTION_CHECK = "Execution Check"
    BROKER_SUBMISSION = "Broker Submission"
    BROKER_ACCEPTANCE = "Broker Acceptance"
    BROKER_FILL = "Broker Fill"
    PORTFOLIO_UPDATE = "Portfolio Update"
    HISTORY = "History"
    JOURNAL = "Journal"
    ANALYTICS = "Analytics"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"


# Map engine stages → lifecycle states used by Execution Intelligence.
STAGE_TO_LIFECYCLE: dict[PipelineStage, LifecycleState] = {
    PipelineStage.DRAFT: LifecycleState.DRAFT,
    PipelineStage.VALIDATION: LifecycleState.VALIDATED,
    PipelineStage.RISK_CHECK: LifecycleState.RISK_APPROVED,
    PipelineStage.EXECUTION_CHECK: LifecycleState.RISK_APPROVED,
    PipelineStage.BROKER_SUBMISSION: LifecycleState.SUBMITTED,
    PipelineStage.BROKER_ACCEPTANCE: LifecycleState.ACCEPTED,
    PipelineStage.BROKER_FILL: LifecycleState.FILLED,
    PipelineStage.PORTFOLIO_UPDATE: LifecycleState.FILLED,
    PipelineStage.HISTORY: LifecycleState.FILLED,
    PipelineStage.JOURNAL: LifecycleState.FILLED,
    PipelineStage.ANALYTICS: LifecycleState.FILLED,
    PipelineStage.REJECTED: LifecycleState.REJECTED,
    PipelineStage.CANCELLED: LifecycleState.CANCELLED,
}
