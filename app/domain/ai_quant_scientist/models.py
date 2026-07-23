"""AQS models — recommendations and scores only."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class RecommendationType(StrEnum):
    OBSERVATION = "Observation"
    INVESTIGATION = "Investigation"
    CANDIDATE_IMPROVEMENT = "Candidate Improvement"
    RISK_WARNING = "Risk Warning"
    OPPORTUNITY = "Opportunity"
    REJECTED_HYPOTHESIS = "Rejected Hypothesis"


class RecommendationStatus(StrEnum):
    OPEN = "Open"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    ARCHIVED = "Archived"


ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "modifies_thresholds": False,
    "modifies_strategy": False,
    "modifies_risk": False,
    "modifies_safety": False,
    "modifies_oms": False,
    "modifies_gateway": False,
    "executes_trades": False,
    "approves_promotion": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "advisory_recommendations_only": True,
    "humans_remain_responsible": True,
}
