"""IRAP models — portfolio risk intelligence (read-only)."""

from __future__ import annotations

from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "modifies_strategy": False,
    "modifies_risk_parameters": False,
    "modifies_safety": False,
    "approves_releases": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "portfolio_risk_intelligence_read_only": True,
}
