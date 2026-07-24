"""Market regime classification for AI Scalping execution behaviour."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import MarketRegimeLabel


@dataclass(frozen=True, slots=True)
class RegimeAssessment:
    regime: MarketRegimeLabel
    confidence: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "regime": self.regime,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
        }


def classify_scalping_regime(
    *,
    alignment_score: int = 0,
    atr_pct: Decimal | None = None,
    bos: int = 0,
    choch: int = 0,
    sweep_count: int = 0,
    range_like: bool = False,
    volume_expanding: bool = False,
) -> RegimeAssessment:
    """Map structure artefacts → scalping regime (deterministic)."""
    reasons: list[str] = []
    high_vol = atr_pct is not None and atr_pct >= Decimal("1.5")
    low_vol = atr_pct is not None and atr_pct <= Decimal("0.4")

    if choch and sweep_count:
        reasons.append("CHOCH + liquidity sweep → reversal")
        return RegimeAssessment("reversal", 78, tuple(reasons))
    if bos and volume_expanding and high_vol:
        reasons.append("BOS + volume expansion → breakout")
        return RegimeAssessment("breakout", 80, tuple(reasons))
    if alignment_score >= 70 and bos and not range_like:
        reasons.append("Aligned MTF + BOS → trending")
        return RegimeAssessment("trending", 82, tuple(reasons))
    if range_like or (low_vol and alignment_score < 55):
        if sweep_count and not bos:
            reasons.append("Sweeps in quiet tape → accumulation")
            return RegimeAssessment("accumulation", 70, tuple(reasons))
        if choch and not bos:
            reasons.append("CHOCH without trend → distribution")
            return RegimeAssessment("distribution", 68, tuple(reasons))
        reasons.append("Low alignment / quiet ATR → range")
        return RegimeAssessment("range", 72, tuple(reasons))
    if high_vol and alignment_score >= 55:
        reasons.append("Elevated ATR with partial alignment → breakout bias")
        return RegimeAssessment("breakout", 65, tuple(reasons))
    reasons.append("Default trending bias from residual alignment")
    return RegimeAssessment("trending", max(50, alignment_score), tuple(reasons))


def regime_from_snapshot_factors(factors: dict[str, Any]) -> RegimeAssessment:
    """Convenience wrapper from confluence / diagnostic factor maps."""
    return classify_scalping_regime(
        alignment_score=int(factors.get("mtf") or factors.get("alignment") or 0),
        atr_pct=(
            Decimal(str(factors["atr_pct"]))
            if factors.get("atr_pct") is not None
            else None
        ),
        bos=int(factors.get("bos") or 0),
        choch=int(factors.get("choch") or 0),
        sweep_count=int(factors.get("sweeps") or 0),
        range_like=bool(factors.get("range_like")),
        volume_expanding=bool(factors.get("volume_expanding")),
    )
