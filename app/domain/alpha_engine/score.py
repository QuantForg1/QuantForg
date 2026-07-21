"""Explainable engine score — never invents values."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

ScoreStatus = Literal["available", "empty", "unavailable"]


@dataclass(frozen=True, slots=True)
class EngineScore:
    engine_id: str
    title: str
    status: ScoreStatus
    score: Decimal | None = None
    passed: bool | None = None
    reasons: tuple[str, ...] = ()
    factors: dict[str, Any] = field(default_factory=dict)
    threshold: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "title": self.title,
            "status": self.status,
            "score": str(self.score) if self.score is not None else None,
            "passed": self.passed,
            "reasons": list(self.reasons),
            "factors": dict(self.factors),
            "threshold": str(self.threshold) if self.threshold is not None else None,
            "explainable": True,
            "invented": False,
        }


def unavailable(
    engine_id: str, title: str, reason: str, *, threshold: Decimal | None = None
) -> EngineScore:
    return EngineScore(
        engine_id=engine_id,
        title=title,
        status="unavailable",
        reasons=(reason,),
        threshold=threshold,
    )


def empty(
    engine_id: str, title: str, reason: str, *, threshold: Decimal | None = None
) -> EngineScore:
    return EngineScore(
        engine_id=engine_id,
        title=title,
        status="empty",
        reasons=(reason,),
        threshold=threshold,
    )


def scored(
    engine_id: str,
    title: str,
    score: Decimal,
    *,
    threshold: Decimal,
    reasons: list[str],
    factors: dict[str, Any] | None = None,
) -> EngineScore:
    clipped = max(Decimal("0"), min(Decimal("100"), score))
    return EngineScore(
        engine_id=engine_id,
        title=title,
        status="available",
        score=clipped.quantize(Decimal("0.01")),
        passed=clipped >= threshold,
        reasons=tuple(reasons),
        factors=dict(factors or {}),
        threshold=threshold,
    )
