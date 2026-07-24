"""Adaptive quality / confidence floors from live ATR%."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from app.domain.institutional_trading.ai_scalping.config import (
    AdaptiveThresholdBand,
    AiScalpingConfig,
    DEFAULT_AI_SCALPING_CONFIG,
    VolatilityBand,
)
from app.domain.institutional_trading.config import ITEConfig


@dataclass(frozen=True, slots=True)
class ResolvedThresholds:
    band: VolatilityBand
    quality: int
    confidence: int
    atr_pct: Decimal | None

    def to_dict(self) -> dict[str, object]:
        return {
            "band": self.band,
            "quality": self.quality,
            "confidence": self.confidence,
            "atr_pct": str(self.atr_pct) if self.atr_pct is not None else None,
        }


def classify_volatility_band(
    atr: Decimal | None,
    mid: Decimal | None,
    *,
    config: AiScalpingConfig | None = None,
) -> tuple[VolatilityBand, Decimal | None]:
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    if atr is None or mid is None or atr <= 0 or mid <= 0:
        return "normal", None
    atr_pct = (atr / mid) * Decimal("100")
    if atr_pct >= cfg.atr_high_pct:
        return "high", atr_pct
    if atr_pct <= cfg.atr_low_pct:
        return "low", atr_pct
    return "normal", atr_pct


def resolve_adaptive_thresholds(
    atr: Decimal | None,
    mid: Decimal | None,
    *,
    config: AiScalpingConfig | None = None,
) -> ResolvedThresholds:
    """Resolve live Quality / Confidence floors — never hardcoded at call sites."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    band, atr_pct = classify_volatility_band(atr, mid, config=cfg)
    profile: AdaptiveThresholdBand
    if band == "high":
        profile = cfg.high_vol
    elif band == "low":
        profile = cfg.low_vol
    else:
        profile = cfg.normal_vol
    return ResolvedThresholds(
        band=band,
        quality=int(profile.quality),
        confidence=int(profile.confidence),
        atr_pct=atr_pct,
    )


def apply_thresholds_to_ite(
    ite: ITEConfig,
    resolved: ResolvedThresholds,
) -> ITEConfig:
    """Return ITEConfig with adaptive mins applied (immutable replace)."""
    return replace(
        ite,
        min_trade_quality_score=resolved.quality,
        min_confluence_score=resolved.confidence,
    )
