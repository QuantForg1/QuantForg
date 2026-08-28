"""Market regime classification for AI Scalping adaptive execution (v6.3).

Continuous labels:
  strong_trend | weak_trend | range | breakout | expansion | compression
"""

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
    """Map structure + volatility artefacts → adaptive scalping regime."""
    reasons: list[str] = []
    high_vol = atr_pct is not None and atr_pct >= Decimal("1.5")
    low_vol = atr_pct is not None and atr_pct <= Decimal("0.4")
    mid_vol = atr_pct is not None and Decimal("0.4") < atr_pct < Decimal("1.5")

    # Compression first — quiet tape dominates behaviour
    if low_vol and (range_like or alignment_score < 55):
        reasons.append("Low ATR% + soft alignment → compression")
        return RegimeAssessment("compression", 74, tuple(reasons))

    # Breakout — structural break with expansion
    if bos and volume_expanding and high_vol:
        reasons.append("BOS + volume + high ATR → breakout")
        return RegimeAssessment("breakout", 82, tuple(reasons))
    if bos and volume_expanding and mid_vol:
        reasons.append("BOS + volume expansion → breakout")
        return RegimeAssessment("breakout", 76, tuple(reasons))

    # Expansion — elevated volatility without clean BOS
    if high_vol and alignment_score >= 50:
        reasons.append("Elevated ATR% with usable alignment → expansion")
        return RegimeAssessment("expansion", 70, tuple(reasons))
    if high_vol:
        reasons.append("Elevated ATR% → expansion (alignment soft)")
        return RegimeAssessment("expansion", 62, tuple(reasons))

    # Strong / weak trend
    if alignment_score >= 75 and bos and not range_like:
        reasons.append("Strong MTF alignment + BOS → strong_trend")
        return RegimeAssessment("strong_trend", 84, tuple(reasons))
    if alignment_score >= 70 and not range_like:
        reasons.append("Strong MTF alignment → strong_trend")
        return RegimeAssessment("strong_trend", 78, tuple(reasons))
    if 55 <= alignment_score < 70 and not range_like:
        reasons.append("Partial MTF alignment → weak_trend")
        return RegimeAssessment("weak_trend", 68, tuple(reasons))

    # Range — including CHOCH/sweep quiet tape (setup family handles reversal)
    if range_like or alignment_score < 55:
        if choch or sweep_count:
            reasons.append("CHOCH/sweeps inside soft tape → range (setup-driven)")
            return RegimeAssessment("range", 70, tuple(reasons))
        reasons.append("Low alignment / quiet structure → range")
        return RegimeAssessment("range", 72, tuple(reasons))

    if low_vol:
        reasons.append("Residual low ATR → compression")
        return RegimeAssessment("compression", 60, tuple(reasons))

    reasons.append("Default weak_trend from residual alignment")
    return RegimeAssessment("weak_trend", max(50, alignment_score), tuple(reasons))


def operator_regime_label(
    regime: str | None,
    *,
    direction: str = "",
    setup_family: str | None = None,
    no_trade: bool = False,
) -> str:
    """Map internal scalping labels to operator TREND_UP/RANGE/… codes.

    Display only. Does not change classification, gates, or execution.
    """
    if no_trade and str(direction or "").upper() not in {"BUY", "SELL", "WAIT"}:
        return "NO_TRADE"
    fam = str(setup_family or "").upper()
    if "RETEST" in fam:
        return "RETEST"
    raw = str(regime or "").strip().lower()
    lean = str(direction or "").strip().upper()
    if raw in {"breakout"}:
        return "BREAKOUT"
    if raw in {"expansion"}:
        return "HIGH_VOLATILITY"
    if raw in {"compression"}:
        return "LOW_LIQUIDITY"
    if raw in {"range"}:
        return "RANGE"
    if raw in {"strong_trend", "weak_trend"}:
        if lean == "SELL":
            return "TREND_DOWN"
        if lean == "BUY":
            return "TREND_UP"
        return "CONFLICT"
    if raw in {"retest"}:
        return "RETEST"
    token = raw.replace(" ", "_").upper()
    return token or "NO_TRADE"


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
