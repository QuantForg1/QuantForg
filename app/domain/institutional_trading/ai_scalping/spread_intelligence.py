"""Spread intelligence - soft confidence penalty; hard reject only at ceiling."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)


@dataclass(frozen=True, slots=True)
class SpreadAssessment:
    score: int  # 0-100
    confidence_penalty: int
    reject: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "confidence_penalty": self.confidence_penalty,
            "reject": self.reject,
            "reason": self.reason,
        }


def assess_spread(
    spread: Decimal | None,
    *,
    atr: Decimal | None = None,
    config: AiScalpingConfig | None = None,
) -> SpreadAssessment:
    """Reject when spread exceeds absolute max OR configured ATR percentage."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    if spread is None:
        return SpreadAssessment(
            score=50,
            confidence_penalty=0,
            reject=False,
            reason="Spread unavailable - neutral",
        )
    if spread > cfg.max_spread_reject:
        return SpreadAssessment(
            score=0,
            confidence_penalty=cfg.spread_soft_penalty_max,
            reject=True,
            reason=(
                f"Spread {spread} exceeds configured reject {cfg.max_spread_reject}"
            ),
        )
    # ATR%-based protection — never enter on FOMO when spread eats the move
    if atr is not None and atr > 0 and cfg.max_spread_atr_pct > 0:
        atr_cap = (atr * cfg.max_spread_atr_pct / Decimal("100")).quantize(
            Decimal("0.0001")
        )
        if spread > atr_cap:
            return SpreadAssessment(
                score=0,
                confidence_penalty=cfg.spread_soft_penalty_max,
                reject=True,
                reason=(
                    f"Spread {spread} exceeds {cfg.max_spread_atr_pct}% of ATR "
                    f"({atr_cap})"
                ),
            )
    if spread <= cfg.max_spread_for_full_score:
        return SpreadAssessment(
            score=100,
            confidence_penalty=0,
            reject=False,
            reason=f"Spread {spread} tight",
        )
    span = cfg.max_spread_reject - cfg.max_spread_for_full_score
    if span <= 0:
        ratio = Decimal("1")
    else:
        ratio = (spread - cfg.max_spread_for_full_score) / span
    ratio = max(Decimal("0"), min(Decimal("1"), ratio))
    score = int(max(0, float(100 * (1 - ratio))))
    penalty = round(float(ratio) * cfg.spread_soft_penalty_max)
    return SpreadAssessment(
        score=score,
        confidence_penalty=penalty,
        reject=False,
        reason=f"Spread {spread} elevated - soft penalty {penalty}",
    )
