"""Session intelligence - soft weight by stars; never hard-block entries."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.session_policy import (
    quality_score_for_stars,
    risk_multiplier_for_stars,
)


@dataclass(frozen=True, slots=True)
class SessionAssessment:
    session: str
    stars: int
    aggressive: bool
    confidence_penalty: int
    quality_score: int
    risk_multiplier: Decimal
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "session": self.session,
            "stars": self.stars,
            "aggressive": self.aggressive,
            "confidence_penalty": self.confidence_penalty,
            "quality_score": self.quality_score,
            "risk_multiplier": str(self.risk_multiplier),
            "reason": self.reason,
        }


def assess_session(
    session: str | None,
    *,
    config: AiScalpingConfig | None = None,
) -> SessionAssessment:
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    key = (session or "off_hours").strip().lower()
    stars = int(cfg.session_stars.get(key, 1))
    aggressive = stars >= cfg.aggressive_session_min_stars
    penalty = 0 if aggressive else int(cfg.weak_session_confidence_penalty)
    quality = quality_score_for_stars(stars)
    risk_mult = risk_multiplier_for_stars(stars)
    reason = (
        f"Session {key} *{stars} - aggressive (riskx={risk_mult})"
        if aggressive
        else (
            f"Session {key} *{stars} - soft-weighted "
            f"(-{penalty} conf, riskx={risk_mult})"
        )
    )
    return SessionAssessment(
        session=key,
        stars=stars,
        aggressive=aggressive,
        confidence_penalty=penalty,
        quality_score=quality,
        risk_multiplier=risk_mult,
        reason=reason,
    )
