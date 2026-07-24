"""CVF models — continuous validation (read-only / evidence only)."""

from __future__ import annotations

from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "modifies_strategy": False,
    "modifies_thresholds": False,
    "modifies_risk": False,
    "modifies_safety": False,
    "modifies_oms": False,
    "modifies_gateway": False,
    "modifies_scheduler": False,
    "approves_promotions": False,
    "triggers_automation": False,
    "writes_production_tables": False,
    "continuous_validation_read_only": True,
    "humans_remain_responsible": True,
}

REGIMES: tuple[str, ...] = (
    "Trending",
    "Ranging",
    "Breakout",
    "Pullback",
    "High Volatility",
    "Low Volatility",
    "Liquidity Sweep",
)

DRIFT_METRICS: tuple[str, ...] = (
    "win_rate",
    "profit_factor",
    "expectancy",
    "drawdown",
    "risk_profile",
    "session",
    "regime",
)
