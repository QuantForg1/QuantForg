"""Institutional Observability Platform — models (monitoring only)."""

from __future__ import annotations

from typing import Literal

ComponentId = Literal[
    "api",
    "gateway",
    "broker",
    "mt5_session",
    "execution_queue",
    "journal_writer",
    "evidence_lab",
    "warehouse",
    "governance",
    "performance_iq",
    "replay_engine",
    "operations_center",
]

COMPONENTS: tuple[ComponentId, ...] = (
    "api",
    "gateway",
    "broker",
    "mt5_session",
    "execution_queue",
    "journal_writer",
    "evidence_lab",
    "warehouse",
    "governance",
    "performance_iq",
    "replay_engine",
    "operations_center",
)

HealthStatus = Literal["healthy", "degraded", "down", "unknown"]

LATENCY_KEYS: tuple[str, ...] = (
    "api",
    "gateway",
    "broker",
    "decision",
    "risk",
    "safety",
    "execution",
    "journal",
    "dashboard",
)

HARD_LOCKS: dict[str, bool] = {
    "observability_only": True,
    "never_modifies_trading_behaviour": True,
    "never_modifies_strategy": True,
    "never_modifies_risk_safety_execution": True,
    "never_modifies_performance_intelligence": True,
    "never_modifies_replay_evidence_lab": True,
    "never_modifies_trading_operations_center": True,
    "never_modifies_audit_governance": True,
    "never_modifies_institutional_data_warehouse": True,
}

# Dependency chain for visualization (top → bottom)
DEPENDENCY_CHAIN: tuple[str, ...] = (
    "frontend",
    "api",
    "gateway",
    "mt5",
    "broker",
    "execution",
    "warehouse",
    "reports",
)
