"""IEP models — research experiment governance (never mutates production)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "modifies_strategies": False,
    "approves_experiments_automatically": False,
    "promotes_experiments_automatically": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "experiment_governance_read_only": True,
    "human_decision_required": True,
}


class ExperimentLifecycle(StrEnum):
    IDEA = "Idea"
    HYPOTHESIS = "Hypothesis"
    EXPERIMENT_DESIGN = "Experiment Design"
    REPLAY = "Replay"
    SIMULATION = "Simulation"
    RISK_ANALYSIS = "Risk Analysis"
    STATISTICAL_VALIDATION = "Statistical Validation"
    AI_REVIEW = "AI Review"
    HUMAN_DECISION = "Human Decision"
    ARCHIVE = "Archive"


LIFECYCLE_ORDER: tuple[str, ...] = tuple(s.value for s in ExperimentLifecycle)

VARIANT_LABELS: tuple[str, ...] = ("Baseline", "Variant A", "Variant B", "Variant C")
