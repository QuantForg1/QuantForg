"""Constants for Continuous Improvement Program."""

from __future__ import annotations

VALIDATION_TARGETS: tuple[str, ...] = (
    "gateway",
    "oms",
    "ai",
    "mt5",
    "risk",
    "portfolio",
    "database",
    "frontend",
    "api",
    "noc",
    "customer_operations",
    "enterprise_platform",
)

TREND_WINDOWS: tuple[str, ...] = ("24h", "7d", "30d", "90d", "1y")

SCORECARD_CATEGORIES: tuple[str, ...] = (
    "reliability",
    "availability",
    "security",
    "trading",
    "operations",
    "support",
    "enterprise",
)

HARD_LOCKS: dict[str, bool] = {
    "modifies_trading": False,
    "modifies_ai": False,
    "modifies_oms": False,
    "modifies_mt5": False,
    "modifies_risk": False,
    "modifies_execution_intelligence": False,
    "modifies_adaptive_intelligence": False,
    "modifies_cop": False,
    "modifies_enterprise_business_rules": False,
    "modifies_auth": False,
    "modifies_pricing": False,
    "additive_only": True,
    "fabricates_metrics": False,
    "observe_only": True,
}
