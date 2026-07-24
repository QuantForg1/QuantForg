"""Session intelligence — aggressive only in top-star sessions."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.institutional_trading.ai_scalping.config import (
    AiScalpingConfig,
    DEFAULT_AI_SCALPING_CONFIG,
)


@dataclass(frozen=True, slots=True)
class SessionAssessment:
    session: str
    stars: int
    aggressive: bool
    confidence_penalty: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "session": self.session,
            "stars": self.stars,
            "aggressive": self.aggressive,
            "confidence_penalty": self.confidence_penalty,
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
    reason = (
        f"Session {key} ★{stars} — aggressive"
        if aggressive
        else f"Session {key} ★{stars} — reduced activity (−{penalty} conf)"
    )
    return SessionAssessment(
        session=key,
        stars=stars,
        aggressive=aggressive,
        confidence_penalty=penalty,
        reason=reason,
    )
