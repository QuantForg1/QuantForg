"""Shared agent types — explainable outputs only."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

Vote = Literal["APPROVE", "HOLD", "REJECT", "ABSTAIN"]


@dataclass(frozen=True, slots=True)
class AgentOutput:
    """Every agent must produce explainable, auditable output."""

    agent: str
    vote: Vote
    confidence: Decimal
    reasons: tuple[str, ...]
    observations: dict[str, Any] = field(default_factory=dict)
    status: str = "available"
    authoritative: bool = False
    never_order_send: bool = True
    explainable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "vote": self.vote,
            "confidence": str(self.confidence),
            "reasons": list(self.reasons),
            "observations": dict(self.observations),
            "status": self.status,
            "authoritative": self.authoritative,
            "never_order_send": True,
            "explainable": True,
        }


@dataclass(frozen=True, slots=True)
class CollaborationInput:
    """Supplied facts — Risk/Safety outcomes from existing engines."""

    side: str = "buy"
    spread: Decimal | None = None
    confidence: Decimal | None = None
    regime: str | None = None
    strategy_id: str | None = None
    strategy_signal: str | None = None
    portfolio_exposure: Decimal | None = None
    open_positions: int | None = None
    execution_mode: str | None = None
    news_blackout: bool | None = None
    kill_switch: bool | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    market_snapshot: dict[str, Any] | None = None
    strategy_snapshot: dict[str, Any] | None = None
    portfolio_snapshot: dict[str, Any] | None = None
    execution_snapshot: dict[str, Any] | None = None
