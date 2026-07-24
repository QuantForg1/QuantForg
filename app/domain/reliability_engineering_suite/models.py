"""RES models — platform reliability analytics (read-only)."""

from __future__ import annotations

from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_strategy": False,
    "modifies_thresholds": False,
    "modifies_risk": False,
    "modifies_safety": False,
    "modifies_oms": False,
    "modifies_gateway": False,
    "modifies_scheduler": False,
    "modifies_production_data": False,
    "triggers_automation": False,
    "writes_production_tables": False,
    "reliability_engineering_read_only": True,
}

SERVICE_NAMES: tuple[str, ...] = (
    "Trading Engine",
    "Risk Engine",
    "Safety Engine",
    "OMS",
    "Gateway",
    "Scheduler",
    "Research",
    "Warehouse",
    "AI Services",
)

FAILURE_CLASSES: tuple[str, ...] = (
    "Gateway Failure",
    "Broker Failure",
    "Scheduler Failure",
    "Strategy Failure",
    "Infrastructure Failure",
    "Data Failure",
    "Unknown",
)
