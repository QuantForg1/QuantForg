"""AQC models — operational explanations and evidence only."""

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
    "modifies_research": False,
    "modifies_production_data": False,
    "triggers_automation": False,
    "approves_promotions": False,
    "writes_production_tables": False,
    "advisory_explanations_only": True,
    "humans_make_all_operational_decisions": True,
}
