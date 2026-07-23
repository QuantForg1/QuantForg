"""QKG models — knowledge graph node/edge types (read-only)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class NodeType(StrEnum):
    TRADE = "Trades"
    SIGNAL = "Signals"
    SESSION = "Sessions"
    MARKET_REGIME = "Market Regimes"
    STRATEGY = "Strategies"
    RESEARCH_EXPERIMENT = "Research Experiments"
    REPLAY_JOB = "Replay Jobs"
    RECOMMENDATION = "Recommendations"
    PORTFOLIO_METRIC = "Portfolio Metrics"
    RISK_EVENT = "Risk Events"
    SAFETY_EVENT = "Safety Events"
    DIAGNOSTIC = "Diagnostics"
    ALERT = "Alerts"
    REPORT = "Reports"


class RelationType(StrEnum):
    GENERATED_BY = "generated_by"
    VALIDATED_BY = "validated_by"
    AFFECTED_BY = "affected_by"
    OBSERVED_IN = "observed_in"
    LINKED_TO = "linked_to"
    DERIVED_FROM = "derived_from"
    CONFIRMED_BY = "confirmed_by"
    CONTRADICTED_BY = "contradicted_by"


ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "modifies_research": False,
    "modifies_risk": False,
    "modifies_strategy": False,
    "modifies_gateway": False,
    "modifies_oms": False,
    "modifies_scheduler": False,
    "modifies_thresholds": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "executes_trades": False,
    "knowledge_layer_read_only": True,
}
