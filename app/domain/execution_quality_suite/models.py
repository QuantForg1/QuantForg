"""EQS models — execution quality analytics (read-only)."""

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
    "modifies_research": False,
    "triggers_automation": False,
    "writes_production_tables": False,
    "execution_intelligence_read_only": True,
}

TIMELINE_STAGES: tuple[str, ...] = (
    "Signal Created",
    "Strategy Approved",
    "Risk Approved",
    "Safety Approved",
    "OMS Submitted",
    "Gateway Sent",
    "Broker Received",
    "Broker Filled",
    "Trade Closed",
)
