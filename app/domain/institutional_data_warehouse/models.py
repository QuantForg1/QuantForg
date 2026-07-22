"""Institutional Data Warehouse — models (analytics infrastructure only)."""

from __future__ import annotations

from typing import Literal

DataDomain = Literal[
    "market",
    "trades",
    "orders",
    "signals",
    "risk",
    "safety",
    "execution",
    "performance",
    "replay",
    "evidence",
    "governance",
    "configuration",
    "reports",
]

DATA_DOMAINS: tuple[DataDomain, ...] = (
    "market",
    "trades",
    "orders",
    "signals",
    "risk",
    "safety",
    "execution",
    "performance",
    "replay",
    "evidence",
    "governance",
    "configuration",
    "reports",
)

HARD_LOCKS: dict[str, bool] = {
    "read_only_warehouse": True,
    "never_modifies_production_records": True,
    "never_modifies_strategy": True,
    "never_modifies_risk_safety_execution": True,
    "never_modifies_performance_intelligence": True,
    "never_modifies_replay_evidence_lab": True,
    "never_modifies_trading_operations_center": True,
    "never_modifies_audit_governance": True,
    "analytics_infrastructure_only": True,
}
