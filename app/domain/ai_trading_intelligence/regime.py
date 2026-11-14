"""Canonical regime taxonomy with UNCERTAIN fail-soft."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any


class CanonicalRegime(StrEnum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    BREAKOUT = "BREAKOUT"
    UNCERTAIN = "UNCERTAIN"


# Minimum confidence (0-100) to accept a non-UNCERTAIN classification.
DEFAULT_MIN_CONFIDENCE = Decimal("55")


_SOURCE_MAP: dict[str, CanonicalRegime] = {
    "strong_trend": CanonicalRegime.TRENDING,
    "weak_trend": CanonicalRegime.TRENDING,
    "trend": CanonicalRegime.TRENDING,
    "trending": CanonicalRegime.TRENDING,
    "trending_up": CanonicalRegime.TRENDING,
    "trending_down": CanonicalRegime.TRENDING,
    "trend_up": CanonicalRegime.TRENDING,
    "trend_down": CanonicalRegime.TRENDING,
    "range": CanonicalRegime.RANGING,
    "ranging": CanonicalRegime.RANGING,
    "pullback": CanonicalRegime.RANGING,
    "breakout": CanonicalRegime.BREAKOUT,
    "expansion": CanonicalRegime.HIGH_VOLATILITY,
    "high_volatility": CanonicalRegime.HIGH_VOLATILITY,
    "high volatility": CanonicalRegime.HIGH_VOLATILITY,
    "news_volatility": CanonicalRegime.HIGH_VOLATILITY,
    "compression": CanonicalRegime.LOW_VOLATILITY,
    "low_volatility": CanonicalRegime.LOW_VOLATILITY,
    "low volatility": CanonicalRegime.LOW_VOLATILITY,
    "unknown": CanonicalRegime.UNCERTAIN,
    "uncertain": CanonicalRegime.UNCERTAIN,
}


@dataclass(frozen=True, slots=True)
class RegimeAssessment:
    regime: CanonicalRegime
    confidence: Decimal
    source_label: str | None
    mapped_from: str | None
    rationale: str
    methodology: dict[str, Any]


def map_canonical_regime(
    source_label: str | None,
    *,
    confidence: Decimal | float | int | None = None,
    min_confidence: Decimal = DEFAULT_MIN_CONFIDENCE,
) -> RegimeAssessment:
    """Map heterogeneous regime labels to the Phase 4 canonical set.

    Insufficient confidence or unknown labels → UNCERTAIN (never force-class).
    """
    conf = Decimal(str(confidence)) if confidence is not None else Decimal("0")
    if conf < 0:
        conf = Decimal("0")
    if conf > 100:
        conf = Decimal("100")

    raw = (source_label or "").strip().lower().replace("-", "_")
    mapped = _SOURCE_MAP.get(raw)
    if mapped is None and raw:
        # Soft contains match
        for key, val in _SOURCE_MAP.items():
            if key in raw or raw in key:
                mapped = val
                break

    if mapped is None:
        return RegimeAssessment(
            regime=CanonicalRegime.UNCERTAIN,
            confidence=conf,
            source_label=source_label,
            mapped_from=None,
            rationale="unrecognized_or_missing_source_label",
            methodology={
                "min_confidence": str(min_confidence),
                "rule": "unknown_label_to_UNCERTAIN",
            },
        )

    if conf < min_confidence:
        return RegimeAssessment(
            regime=CanonicalRegime.UNCERTAIN,
            confidence=conf,
            source_label=source_label,
            mapped_from=mapped.value,
            rationale=f"confidence_below_{min_confidence}",
            methodology={
                "min_confidence": str(min_confidence),
                "rule": "low_confidence_to_UNCERTAIN",
                "would_have_been": mapped.value,
            },
        )

    return RegimeAssessment(
        regime=mapped,
        confidence=conf,
        source_label=source_label,
        mapped_from=mapped.value,
        rationale="mapped_from_source",
        methodology={
            "min_confidence": str(min_confidence),
            "rule": "direct_map",
        },
    )
