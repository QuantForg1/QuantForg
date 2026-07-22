"""Shared types for Alpha Factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class ModuleResult:
    module: str
    status: str
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
            "outside_production": True,
            "never_order_send": True,
            "never_auto_promotes": True,
            "promise_profitability": False,
        }


@dataclass(frozen=True, slots=True)
class AlphaFactoryInput:
    """Research facts only — never invents bars, trades, or metrics."""

    action: str = "evaluate"
    # Experiment / strategy
    experiment: dict[str, Any] | None = None
    experiments: list[dict[str, Any]] | None = None
    strategy: dict[str, Any] | None = None
    strategies: list[dict[str, Any]] | None = None
    # Replay (supplied results or bars metadata)
    replay: dict[str, Any] | None = None
    # Paper trading (supplied paper results)
    paper: dict[str, Any] | None = None
    # Benchmark candidates
    benchmarks: list[dict[str, Any]] | None = None
    # Promotion
    promotion: dict[str, Any] | None = None
    # History append
    history_event: dict[str, Any] | None = None
    # Alpha score dimensions (optional supplied)
    score_inputs: dict[str, Any] | None = None
    author: str | None = None
