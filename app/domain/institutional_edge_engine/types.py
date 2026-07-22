"""Shared types for Institutional Edge Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class ModuleResult:
    module: str
    status: str  # available | insufficient_data | empty
    score: Decimal | None
    recommendation: str
    reasons: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "status": self.status,
            "score": str(self.score) if self.score is not None else None,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
            "details": dict(self.details),
            "explainable": True,
            "invented": False,
            "never_order_send": True,
            "never_disables_trading": True,
            "auto_modifies_strategy_rules": False,
            "promise_profitability": False,
        }


@dataclass(frozen=True, slots=True)
class IeeInput:
    """Completed trades and discipline facts — never invents metrics."""

    completed_trades: list[dict[str, Any]] | None = None
    discipline_facts: dict[str, Any] | None = None
    prior_edge_score: Decimal | None = None
    research_month: str | None = None
