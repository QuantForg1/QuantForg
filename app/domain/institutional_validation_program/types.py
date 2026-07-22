"""Shared types for Institutional Validation Program."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class ModuleResult:
    module: str
    status: str  # available | insufficient_evidence | empty
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
            "read_only": True,
            "never_places_trades": True,
            "never_auto_promotes": True,
            "promise_profitability": False,
        }


@dataclass(frozen=True, slots=True)
class IvpInput:
    """Evidence inputs only — never invents trades or metrics."""

    completed_trades: list[dict[str, Any]] | None = None
    configurations: list[dict[str, Any]] | None = None
    risk_facts: dict[str, Any] | None = None
    replay_results: dict[str, Any] | None = None
    paper_results: dict[str, Any] | None = None
    strategy_id: str | None = None
    configuration_id: str | None = None
    history_event: dict[str, Any] | None = None
