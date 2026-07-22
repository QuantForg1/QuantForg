"""Shared types for Adaptive Scalping Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class ModuleResult:
    module: str
    status: str  # available | empty | insufficient_history
    source: str  # live | historical | mixed | none
    score: Decimal | None
    recommendation: str
    reasons: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "status": self.status,
            "source": self.source,
            "score": str(self.score) if self.score is not None else None,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
            "details": dict(self.details),
            "explainable": True,
            "invented": False,
            "never_order_send": True,
            "auto_modifies_rules": False,
            "promise_profitability": False,
        }


@dataclass(frozen=True, slots=True)
class AsiInput:
    """Supplied facts only — never invents market or historical stats."""

    side: str = "buy"
    # Live observations
    session: str | None = None
    hour_utc: int | None = None
    weekday: str | None = None
    regime: str | None = None
    volatility: str | None = None
    spread: Decimal | None = None
    personality_hint: str | None = None
    pattern_id: str | None = None
    live_confidence: Decimal | None = None
    live_opportunity: dict[str, Any] | None = None
    capital_facts: dict[str, Any] | None = None
    decision_context: dict[str, Any] | None = None
    # Historical observations stored by the platform (caller-supplied)
    historical_observations: list[dict[str, Any]] | None = None
    closed_trades: list[dict[str, Any]] | None = None
    opportunity_catalog: list[dict[str, Any]] | None = None
