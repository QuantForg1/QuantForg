"""Shared types for Institutional Trading Brain V3."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class ModuleResult:
    """Explainable module output — never invents facts."""

    module: str
    status: str
    score: Decimal | None
    passed: bool | None
    recommendation: str
    reasons: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)
    invented: bool = False
    explainable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "status": self.status,
            "score": str(self.score) if self.score is not None else None,
            "passed": self.passed,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
            "details": dict(self.details),
            "invented": False,
            "explainable": True,
            "never_order_send": True,
            "promise_profitability": False,
        }


@dataclass(frozen=True, slots=True)
class BrainInput:
    """Supplied facts only — missing data → unavailable / No Trade."""

    side: str = "buy"
    spread: Decimal | None = None
    atr: Decimal | None = None
    regime: str | None = None
    session: str | None = None
    news_blackout: bool | None = None
    kill_switch: bool | None = None
    confidence: Decimal | None = None
    opportunity_candidates: list[dict[str, Any]] | None = None
    decision_center: dict[str, Any] | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    execution_mode: str | None = None
    open_positions: int | None = None
    unrealized_pnl: Decimal | None = None
    active_trade: dict[str, Any] | None = None
    closed_trades: list[dict[str, Any]] | None = None
    quality_metrics: dict[str, Any] | None = None
    operator_notes: list[str] | None = None
