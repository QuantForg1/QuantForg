"""QEM models — institutional event mesh (read-only distribution)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "modifies_strategies": False,
    "modifies_risk": False,
    "approves_releases": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "event_distribution_read_only": True,
    "events_immutable": True,
}


class EventType(StrEnum):
    STRATEGY_CREATED = "StrategyCreated"
    STRATEGY_UPDATED = "StrategyUpdated"
    REPLAY_COMPLETED = "ReplayCompleted"
    SIMULATION_COMPLETED = "SimulationCompleted"
    EXPERIMENT_COMPLETED = "ExperimentCompleted"
    VALIDATION_COMPLETED = "ValidationCompleted"
    CERTIFICATION_COMPLETED = "CertificationCompleted"
    RELEASE_CREATED = "ReleaseCreated"
    RELEASE_APPROVED = "ReleaseApproved"
    RELEASE_ROLLED_BACK = "ReleaseRolledBack"
    PORTFOLIO_UPDATED = "PortfolioUpdated"
    RISK_ALERT = "RiskAlert"
    EXECUTION_ALERT = "ExecutionAlert"
    RELIABILITY_ALERT = "ReliabilityAlert"
    PLATFORM_ALERT = "PlatformAlert"


EVENT_TYPES: tuple[str, ...] = tuple(e.value for e in EventType)

EVENT_SOURCES: tuple[str, ...] = (
    "trading_engine",
    "oms",
    "gateway",
    "research_lab",
    "replay",
    "simulation",
    "cvf",
    "irap",
    "qcs",
    "qpm",
    "islm",
    "irdp",
    "aoc",
    "icp",
    "knowledge_graph",
)

# Declarative subscribers — routing catalog only, never tight coupling
DEFAULT_SUBSCRIBERS: tuple[dict[str, Any], ...] = (
    {"subscriber_id": "aoc", "categories": ["alert", "certification", "release"], "mode": "observe"},
    {"subscriber_id": "icp", "categories": ["alert", "platform"], "mode": "observe"},
    {"subscriber_id": "qcs", "categories": ["validation", "simulation", "replay"], "mode": "observe"},
    {"subscriber_id": "qpm", "categories": ["portfolio", "strategy", "risk"], "mode": "observe"},
    {"subscriber_id": "islm", "categories": ["strategy", "experiment", "certification"], "mode": "observe"},
    {"subscriber_id": "audit_ledger", "categories": ["*"], "mode": "immutable_audit"},
)
