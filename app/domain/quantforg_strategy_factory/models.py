"""QSF models — QuantForg Strategy Factory (governed workflow)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "approves_releases": False,
    "deploys_strategies": False,
    "allocates_capital": False,
    "human_approval_required_for_transitions": True,
    "preserves_existing_safety_guarantees": True,
    "writes_production_tables": False,
    "factory_isolated": True,
}


class PipelineStage(StrEnum):
    IDEA = "Idea"
    HYPOTHESIS = "Hypothesis"
    RESEARCH = "Research"
    EXPERIMENT = "Experiment"
    REPLAY = "Replay"
    SIMULATION = "Simulation"
    CONTINUOUS_VALIDATION = "Continuous Validation"
    RISK_REVIEW = "Risk Review"
    CERTIFICATION = "Certification"
    DECISION_INTELLIGENCE = "Decision Intelligence"
    PAPER_TRADING_READY = "Paper Trading Ready"


PIPELINE_STAGES: tuple[str, ...] = tuple(s.value for s in PipelineStage)

# Ordered progression for transition validation
PIPELINE_ORDER: tuple[str, ...] = PIPELINE_STAGES

INTEGRATIONS: tuple[str, ...] = (
    "irl",
    "iep",
    "replay",
    "ise",
    "cvf",
    "irap",
    "qcs",
    "qdie",
    "islm",
    "qsmr",
    "qkg",
    "qem",
    "qcdm",
)

WORK_ITEM_STATUSES: tuple[str, ...] = (
    "queued",
    "in_progress",
    "blocked",
    "awaiting_approval",
    "approved",
    "rejected",
    "done",
)

DOSSIER_KINDS: tuple[str, ...] = (
    "strategy_dossier",
    "research_dossier",
    "validation_dossier",
    "certification_dossier",
    "paper_trading_dossier",
)
