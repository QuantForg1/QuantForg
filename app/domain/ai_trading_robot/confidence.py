"""AI confidence scoring — advisory; never alone authorizes execution."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.ai_trading_robot.config import RobotV1Config


@dataclass(frozen=True, slots=True)
class ConfidenceScore:
    score: Decimal
    band: str  # low | medium | high | blocked
    passed: bool
    factors: dict[str, Decimal]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "score": str(self.score),
            "band": self.band,
            "passed": self.passed,
            "factors": {k: str(v) for k, v in self.factors.items()},
            "reasons": list(self.reasons),
        }


def score_ai_confidence(
    config: RobotV1Config,
    *,
    confluence: Decimal | None = None,
    trade_quality: Decimal | None = None,
    structure_bias_aligned: bool | None = None,
    spread_ok: bool = True,
    volatility_ok: bool = True,
    strategy_health: Decimal | None = None,
) -> ConfidenceScore:
    """Composite 0-100 confidence. Fail closed below min_confidence."""
    factors: dict[str, Decimal] = {}
    score = Decimal("50")
    reasons: list[str] = []

    if confluence is not None:
        c = max(Decimal("0"), min(Decimal("100"), confluence))
        factors["confluence"] = c
        score = score + (c - Decimal("50")) * Decimal("0.35")
    else:
        reasons.append("Confluence not supplied — neutral weight.")

    if trade_quality is not None:
        q = max(Decimal("0"), min(Decimal("100"), trade_quality))
        factors["trade_quality"] = q
        score = score + (q - Decimal("50")) * Decimal("0.25")
    else:
        reasons.append("Trade quality not supplied — neutral weight.")

    if strategy_health is not None:
        h = max(Decimal("0"), min(Decimal("100"), strategy_health))
        factors["strategy_health"] = h
        score = score + (h - Decimal("50")) * Decimal("0.20")

    if structure_bias_aligned is True:
        factors["structure_align"] = Decimal("10")
        score += Decimal("8")
    elif structure_bias_aligned is False:
        factors["structure_align"] = Decimal("-10")
        score -= Decimal("12")
        reasons.append("Structure bias not aligned with signal direction.")

    if not spread_ok:
        score -= Decimal("15")
        reasons.append("Spread filter failed — confidence penalized.")
    if not volatility_ok:
        score -= Decimal("10")
        reasons.append("Volatility filter failed — confidence penalized.")

    score = max(Decimal("0"), min(Decimal("100"), score)).quantize(Decimal("0.01"))
    if score >= 75:
        band = "high"
    elif score >= 55:
        band = "medium"
    elif score >= config.min_confidence:
        band = "low"
    else:
        band = "blocked"

    passed = score >= config.min_confidence
    if not passed:
        reasons.append(
            f"Confidence {score} below minimum {config.min_confidence}."
        )
    return ConfidenceScore(
        score=score,
        band=band,
        passed=passed,
        factors=factors,
        reasons=tuple(reasons),
    )
