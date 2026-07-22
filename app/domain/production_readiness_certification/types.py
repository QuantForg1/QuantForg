"""Shared types for Production Readiness Certification."""

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
            "certifies_only": True,
            "never_places_trades": True,
            "never_changes_configuration": True,
            "promise_profitability": False,
        }


@dataclass(frozen=True, slots=True)
class PrcInput:
    """Caller-supplied evidence only — never invents operational metrics."""

    reliability: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    data: dict[str, Any] | None = None
    research: dict[str, Any] | None = None
    operations: dict[str, Any] | None = None
    prior_certification_status: str | None = None
