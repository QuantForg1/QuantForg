"""Institutional Confidence Score (0-100)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_ai_decision.config import DecisionEngineV1Config
from app.domain.institutional_ai_decision.layers import LayerResult


@dataclass(frozen=True, slots=True)
class InstitutionalConfidence:
    score: Decimal
    band: str  # blocked | low | medium | high
    passed: bool
    layer_score: Decimal
    adjustments: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "score": str(self.score),
            "band": self.band,
            "passed": self.passed,
            "layer_score": str(self.layer_score),
            "adjustments": list(self.adjustments),
        }


def score_institutional_confidence(
    config: DecisionEngineV1Config,
    layers: tuple[LayerResult, ...],
    *,
    strategy_health: Decimal | None = None,
    consecutive_losses: int = 0,
    daily_drawdown_pct: Decimal = Decimal("0"),
) -> InstitutionalConfidence:
    """Weighted layer sum scaled to 0-100, then discipline penalties."""
    total_weight = sum((layer.weight for layer in layers), Decimal("0"))
    raw = sum((layer.score_contrib for layer in layers), Decimal("0"))
    layer_score = (
        (raw / total_weight * Decimal("100")).quantize(Decimal("0.01"))
        if total_weight > 0
        else Decimal("0")
    )
    score = layer_score
    adjustments: list[str] = []

    if strategy_health is not None:
        if strategy_health < config.min_health_score:
            score -= Decimal("10")
            adjustments.append(
                f"Strategy health {strategy_health} below min "
                f"{config.min_health_score} (-10)."
            )
        elif strategy_health >= Decimal("70"):
            score += Decimal("5")
            adjustments.append(f"Strategy health {strategy_health} supportive (+5).")

    if consecutive_losses > 0:
        pen = Decimal(min(consecutive_losses, 5)) * Decimal("4")
        score -= pen
        adjustments.append(f"Consecutive losses {consecutive_losses} (-{pen}).")

    if daily_drawdown_pct > 0:
        pen = (daily_drawdown_pct * Decimal("3")).quantize(Decimal("0.01"))
        score -= pen
        adjustments.append(f"Daily drawdown {daily_drawdown_pct}% (-{pen}).")

    # Hard block if required Risk/Safety failed
    risk = next((layer for layer in layers if layer.name == "risk"), None)
    safety = next((layer for layer in layers if layer.name == "safety"), None)
    if risk is not None and not risk.passed:
        score = min(score, config.min_confidence - Decimal("1"))
        adjustments.append("Risk layer failed — confidence capped below minimum.")
    if safety is not None and not safety.passed:
        score = min(score, config.min_confidence - Decimal("1"))
        adjustments.append("Safety layer failed — confidence capped below minimum.")

    score = max(Decimal("0"), min(Decimal("100"), score)).quantize(Decimal("0.01"))
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
        adjustments.append(
            f"Confidence {score} below institutional minimum {config.min_confidence}."
        )
    return InstitutionalConfidence(
        score=score,
        band=band,
        passed=passed,
        layer_score=layer_score,
        adjustments=tuple(adjustments),
    )
