"""Shared types for Real Market Intelligence Platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class ModuleResult:
    module: str
    status: str  # available | missing_data | empty
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
            "context_only": True,
            "never_places_trades": True,
            "never_changes_trading_rules": True,
            "promise_profitability": False,
        }


@dataclass(frozen=True, slots=True)
class RmipInput:
    """Caller-supplied observations only — never invents feeds."""

    economic_events: list[dict[str, Any]] | None = None
    clock_utc: str | None = None
    session_hint: str | None = None
    volatility_observations: dict[str, Any] | None = None
    liquidity_observations: dict[str, Any] | None = None
    regime: str | None = None
    trend: str | None = None
    confidence: str | None = None
    archive_event: dict[str, Any] | None = None
