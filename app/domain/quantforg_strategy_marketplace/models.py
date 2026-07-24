"""QSMR models — strategy marketplace & registry (never mutates production)."""

from __future__ import annotations

from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_strategies": False,
    "modifies_production": False,
    "approves_certifications": False,
    "deploys_strategies": False,
    "writes_production_tables": False,
    "triggers_automation": False,
    "registry_read_only": True,
}

SCORE_KEYS: tuple[str, ...] = (
    "overall_strategy_score",
    "research_score",
    "validation_score",
    "risk_score",
    "execution_score",
    "certification_score",
)

SORT_FIELDS: tuple[str, ...] = (
    "overall_strategy_score",
    "research_score",
    "validation_score",
    "risk_score",
    "execution_score",
    "certification_score",
    "strategy_name",
    "version",
    "lifecycle",
    "owner",
    "updated_at",
)

GROUP_FIELDS: tuple[str, ...] = (
    "owner",
    "status",
    "lifecycle",
    "certification_status",
    "retirement_status",
)
