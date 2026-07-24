"""QPM models — portfolio orchestration (never mutates production)."""

from __future__ import annotations

from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "changes_strategy_parameters": False,
    "rebalances_automatically": False,
    "allocates_capital_automatically": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "portfolio_orchestration_read_only": True,
    "human_approval_required_for_actions": True,
}

RECOMMENDATION_KINDS: tuple[str, ...] = (
    "Increase allocation",
    "Reduce allocation",
    "Suspend allocation",
    "Retire strategy candidate",
    "Research candidate",
)

METRIC_KEYS: tuple[str, ...] = (
    "portfolio_sharpe",
    "portfolio_sortino",
    "portfolio_drawdown",
    "capital_utilization",
    "diversification_score",
    "correlation_risk",
    "expected_portfolio_return",
    "portfolio_confidence_score",
)
