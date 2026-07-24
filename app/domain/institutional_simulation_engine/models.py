"""ISE models — institutional simulation engine (fully isolated)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_strategies": False,
    "modifies_thresholds": False,
    "modifies_risk": False,
    "modifies_safety": False,
    "modifies_oms": False,
    "modifies_gateway": False,
    "modifies_scheduler": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "digital_twin_isolated": True,
    "simulation_laboratory_only": True,
}

PIPELINE_STAGES: tuple[str, ...] = (
    "Market",
    "Signal",
    "MTF",
    "Quality",
    "Confluence",
    "Risk",
    "Safety",
    "OMS",
    "Gateway",
    "Execution",
)


class SimulationMode(StrEnum):
    HISTORICAL_REPLAY = "Historical Replay"
    WALK_FORWARD = "Historical Walk Forward"
    STRESS_TEST = "Historical Stress Test"
    SCENARIO_BUILDER = "Historical Scenario Builder"
    MONTE_CARLO = "Historical Monte Carlo"


SCENARIO_KEYS: tuple[str, ...] = (
    "higher_spread",
    "lower_spread",
    "broker_delay",
    "higher_volatility",
    "lower_volatility",
    "london_disabled",
    "ny_disabled",
    "atr_scaling",
    "risk_scaling",
    "execution_delay",
    "liquidity_reduction",
    "session_changes",
)

STRESS_KEYS: tuple[str, ...] = (
    "extreme_spread",
    "execution_delay",
    "volatility_spike",
    "low_liquidity",
    "gap",
    "rapid_trend",
    "rapid_reversal",
)

MONTE_CARLO_PATHS: tuple[int, ...] = (100, 500, 1000, 5000)
