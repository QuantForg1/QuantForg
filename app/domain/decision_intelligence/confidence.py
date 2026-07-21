"""Confidence breakdown — factor scores from supplied inputs only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.decision_intelligence.config import DecisionIntelligenceConfig


@dataclass(frozen=True, slots=True)
class ConfidenceFactors:
    signal_strength: Decimal | None = None
    structure_align: Decimal | None = None
    consensus: Decimal | None = None
    regime_fit: Decimal | None = None
    execution_quality: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ConfidenceBreakdown:
    score: Decimal
    band: str
    passed: bool
    factors: dict[str, Decimal | None]
    reasons: tuple[str, ...]
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "score": str(self.score),
            "band": self.band,
            "passed": self.passed,
            "factors": {
                k: (str(v) if v is not None else None)
                for k, v in self.factors.items()
            },
            "reasons": list(self.reasons),
            "status": self.status,
        }


def breakdown_confidence(
    config: DecisionIntelligenceConfig, factors: ConfidenceFactors
) -> ConfidenceBreakdown:
    values = [
        factors.signal_strength,
        factors.structure_align,
        factors.consensus,
        factors.regime_fit,
        factors.execution_quality,
    ]
    present = [v for v in values if v is not None]
    if not present:
        return ConfidenceBreakdown(
            score=Decimal("0"),
            band="blocked",
            passed=False,
            factors={
                "signal_strength": factors.signal_strength,
                "structure_align": factors.structure_align,
                "consensus": factors.consensus,
                "regime_fit": factors.regime_fit,
                "execution_quality": factors.execution_quality,
            },
            reasons=("No confidence factors supplied — fail closed.",),
            status="unavailable",
        )

    score = (
        sum(present, Decimal("0")) / Decimal(len(present))
    ).quantize(Decimal("0.01"))
    reasons = [f"Averaged {len(present)} supplied confidence factors."]
    if score >= config.high_confidence:
        band = "high"
    elif score >= config.min_confidence:
        band = "medium"
    elif score >= Decimal("40"):
        band = "low"
    else:
        band = "blocked"
    passed = score >= config.min_confidence
    if not passed:
        reasons.append(
            f"Score {score} below policy minimum {config.min_confidence}."
        )
    return ConfidenceBreakdown(
        score=score,
        band=band,
        passed=passed,
        factors={
            "signal_strength": factors.signal_strength,
            "structure_align": factors.structure_align,
            "consensus": factors.consensus,
            "regime_fit": factors.regime_fit,
            "execution_quality": factors.execution_quality,
        },
        reasons=tuple(reasons),
        status="available",
    )
