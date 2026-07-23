"""Institutional Data Warehouse — models (analytics infrastructure only)."""

from __future__ import annotations

from typing import Literal

# Expanded analytical domains — warehouse copies only; never production tables.
DataDomain = Literal[
    "market",
    "signals",
    "strategy_decisions",
    "risk",
    "safety",
    "oms",
    "execution",
    "gateway",
    "broker",
    "replay",
    "research",
    "portfolio",
    "regimes",
    "opportunity",
    "diagnostics",
    "audit",
    # Legacy aliases retained for compatibility
    "trades",
    "orders",
    "performance",
    "evidence",
    "governance",
    "configuration",
    "reports",
]

DATA_DOMAINS: tuple[DataDomain, ...] = (
    "market",
    "signals",
    "strategy_decisions",
    "risk",
    "safety",
    "oms",
    "execution",
    "gateway",
    "broker",
    "replay",
    "research",
    "portfolio",
    "regimes",
    "opportunity",
    "diagnostics",
    "audit",
    "trades",
    "orders",
    "performance",
    "evidence",
    "governance",
    "configuration",
    "reports",
)

FACT_TABLES: tuple[str, ...] = (
    "fact_trades",
    "fact_signals",
    "fact_executions",
    "fact_research",
    "fact_portfolio",
    "fact_risk",
    "fact_diagnostics",
)

DIMENSION_TABLES: tuple[str, ...] = (
    "dim_time",
    "dim_session",
    "dim_strategy",
    "dim_regime",
    "dim_instrument",
)

RETENTION_TIERS: tuple[str, ...] = ("raw_events", "aggregates", "archive")

HARD_LOCKS: dict[str, bool] = {
    "read_only_warehouse": True,
    "never_modifies_production_records": True,
    "never_modifies_strategy": True,
    "never_modifies_risk_safety_execution": True,
    "never_modifies_oms_gateway_auto_trading": True,
    "never_modifies_performance_intelligence": True,
    "never_modifies_replay_evidence_lab": True,
    "never_modifies_trading_operations_center": True,
    "never_modifies_audit_governance": True,
    "analytics_infrastructure_only": True,
    "immutable_event_storage": True,
}
