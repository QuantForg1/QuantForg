"""Regime-aware execution profiles — adjust RR / trail / hold / partial safely.

Never loosens quality floors or raises risk. High-vol and ranging regimes
tighten behaviour; trending may allow slightly longer holds within absolute max.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
    MarketRegimeLabel,
)
from app.domain.institutional_trading.ai_scalping.regime import RegimeAssessment

VolatilityBand = Literal["high", "normal", "low"]


def _vol_from_atr_pct(
    atr_pct: Decimal | None,
    *,
    config: AiScalpingConfig,
) -> VolatilityBand:
    if atr_pct is None:
        return "normal"
    if atr_pct >= config.atr_high_pct:
        return "high"
    if atr_pct <= config.atr_low_pct:
        return "low"
    return "normal"


@dataclass(frozen=True, slots=True)
class RegimeExecutionProfile:
    """Execution knobs derived from market regime (safety-preserving)."""

    regime: MarketRegimeLabel
    volatility: VolatilityBand
    min_expected_rr: Decimal
    trail_after_r: Decimal
    absolute_max_hold_minutes: int
    time_stop_minutes: int
    partial_tp_enabled: bool
    partial_at_r: Decimal
    partial_close_pct: Decimal
    trail_atr_mult_scale: Decimal
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "volatility": self.volatility,
            "min_expected_rr": str(self.min_expected_rr),
            "trail_after_r": str(self.trail_after_r),
            "absolute_max_hold_minutes": self.absolute_max_hold_minutes,
            "time_stop_minutes": self.time_stop_minutes,
            "partial_tp_enabled": self.partial_tp_enabled,
            "partial_at_r": str(self.partial_at_r),
            "partial_close_pct": str(self.partial_close_pct),
            "trail_atr_mult_scale": str(self.trail_atr_mult_scale),
            "reasons": list(self.reasons),
        }


def build_regime_execution_profile(
    assessment: RegimeAssessment,
    *,
    atr_pct: Decimal | None = None,
    config: AiScalpingConfig | None = None,
) -> RegimeExecutionProfile:
    """Map regime + volatility → execution profile without reducing safety."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    vol = _vol_from_atr_pct(atr_pct, config=cfg)
    reasons: list[str] = list(assessment.reasons)
    reasons.append(f"Volatility band={vol}")
    min_rr = cfg.min_expected_rr
    trail_after = cfg.trail_after_r
    abs_hold = cfg.absolute_max_hold_minutes
    time_stop = cfg.time_stop_minutes
    partial_enabled = cfg.partial_tp_enabled
    partial_at = cfg.partial_at_r
    partial_pct = cfg.partial_close_pct
    trail_scale = Decimal("1.0")

    regime = assessment.regime

    if vol == "high":
        # Widen trail, shorten hold, demand slightly higher RR — never lower RR floor
        min_rr = max(min_rr, cfg.min_expected_rr + Decimal("0.2"))
        trail_after = max(trail_after, cfg.trail_after_r)
        abs_hold = max(cfg.typical_hold_max_minutes, min(abs_hold, 15))
        time_stop = min(time_stop, max(5, abs_hold // 2))
        trail_scale = Decimal("1.35")
        partial_at = min(partial_at, Decimal("0.8"))
        reasons.append("High vol → shorter hold, wider trail, higher RR floor")
    elif vol == "low":
        # Quiet tape: keep holds short, trail sooner, no FOMO lengthening
        abs_hold = min(abs_hold, cfg.typical_hold_max_minutes)
        time_stop = min(time_stop, cfg.typical_hold_max_minutes)
        trail_after = min(trail_after, Decimal("0.8"))
        trail_scale = Decimal("0.85")
        reasons.append("Low vol → early trail, capped hold")

    if regime in {"range", "accumulation", "distribution"}:
        min_rr = max(min_rr, cfg.min_expected_rr + Decimal("0.1"))
        abs_hold = min(abs_hold, cfg.typical_hold_max_minutes)
        partial_enabled = True
        partial_pct = max(partial_pct, Decimal("50"))
        trail_after = min(trail_after, Decimal("0.8"))
        reasons.append("Ranging → faster scale-out, tighter hold")
    elif regime in {"trending", "breakout"}:
        # Allow hold up to configured absolute max only (never beyond)
        abs_hold = min(cfg.absolute_max_hold_minutes, max(abs_hold, cfg.typical_hold_max_minutes))
        if vol != "high":
            trail_after = max(trail_after, cfg.trail_after_r)
        reasons.append("Trending/breakout → structure trail preferred, hold within max")
    elif regime == "reversal":
        abs_hold = min(abs_hold, max(8, cfg.typical_hold_max_minutes))
        partial_enabled = True
        partial_at = min(partial_at, Decimal("0.7"))
        reasons.append("Reversal → early partial, short hold")

    # Hard safety clamps
    if min_rr < cfg.min_expected_rr:
        min_rr = cfg.min_expected_rr
    if abs_hold > cfg.absolute_max_hold_minutes:
        abs_hold = cfg.absolute_max_hold_minutes
    if abs_hold < cfg.typical_hold_min_minutes:
        abs_hold = cfg.typical_hold_min_minutes
    if time_stop > abs_hold:
        time_stop = abs_hold

    return RegimeExecutionProfile(
        regime=regime,
        volatility=vol,
        min_expected_rr=min_rr,
        trail_after_r=trail_after,
        absolute_max_hold_minutes=abs_hold,
        time_stop_minutes=time_stop,
        partial_tp_enabled=partial_enabled,
        partial_at_r=partial_at,
        partial_close_pct=partial_pct,
        trail_atr_mult_scale=trail_scale,
        reasons=tuple(reasons),
    )
