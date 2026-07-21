"""Market regime detection from provided analysis inputs only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.domain.market_intelligence.config import MarketIntelligenceConfig


class MarketRegime(StrEnum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    NEWS_DRIVEN = "news_driven"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RegimeInput:
    """Caller-supplied structure/volatility/news — never fabricated."""

    trend: str | None = None  # up | down | ranging | neutral
    atr: Decimal | None = None
    price: Decimal | None = None
    news_driven: bool | None = None
    structure_label: str | None = None


@dataclass(frozen=True, slots=True)
class RegimeAssessment:
    primary: MarketRegime
    regimes: tuple[MarketRegime, ...]
    evidence: tuple[str, ...]
    status: str  # available | unavailable
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "primary": self.primary.value,
            "regimes": [r.value for r in self.regimes],
            "evidence": list(self.evidence),
            "status": self.status,
            "reason": self.reason,
            "advisory_only": True,
        }


def detect_market_regime(
    config: MarketIntelligenceConfig, inp: RegimeInput
) -> RegimeAssessment:
    """Classify regime from real inputs. Empty when insufficient data."""
    evidence: list[str] = []
    regimes: list[MarketRegime] = []

    trend = (inp.trend or "").strip().lower()
    if trend in {"up", "bullish", "trending_up"}:
        regimes.append(MarketRegime.TRENDING_UP)
        evidence.append(f"Trend input={inp.trend}")
    elif trend in {"down", "bearish", "trending_down"}:
        regimes.append(MarketRegime.TRENDING_DOWN)
        evidence.append(f"Trend input={inp.trend}")
    elif trend in {"ranging", "range", "neutral", "sideways"}:
        regimes.append(MarketRegime.RANGING)
        evidence.append(f"Trend input={inp.trend}")

    if inp.structure_label:
        evidence.append(f"Structure={inp.structure_label}")

    atr_pct: Decimal | None = None
    if inp.atr is not None and inp.price is not None and inp.price > 0:
        atr_pct = (inp.atr / inp.price * Decimal("100")).quantize(Decimal("0.01"))
        evidence.append(f"ATR%={atr_pct}")
        if atr_pct >= config.high_vol_atr_pct:
            regimes.append(MarketRegime.HIGH_VOLATILITY)
            evidence.append(
                f"High volatility (>= {config.high_vol_atr_pct}% ATR)"
            )
        elif atr_pct <= config.low_vol_atr_pct:
            regimes.append(MarketRegime.LOW_VOLATILITY)
            evidence.append(
                f"Low volatility (<= {config.low_vol_atr_pct}% ATR)"
            )

    if inp.news_driven is True:
        regimes.append(MarketRegime.NEWS_DRIVEN)
        evidence.append("News-driven flag supplied by caller")
    elif inp.news_driven is False:
        evidence.append("News-driven flag false")

    # Deduplicate preserve order
    seen: set[MarketRegime] = set()
    ordered: list[MarketRegime] = []
    for regime in regimes:
        if regime not in seen:
            seen.add(regime)
            ordered.append(regime)

    if not ordered:
        return RegimeAssessment(
            primary=MarketRegime.UNKNOWN,
            regimes=(),
            evidence=tuple(evidence)
            or ("Insufficient inputs for regime classification",),
            status="unavailable",
            reason="Insufficient structure/volatility/news inputs — no invented regime",
        )

    return RegimeAssessment(
        primary=ordered[0],
        regimes=tuple(ordered),
        evidence=tuple(evidence),
        status="available",
        reason=f"Primary regime {ordered[0].value} from supplied inputs",
    )
