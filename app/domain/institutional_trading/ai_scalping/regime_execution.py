"""Regime-aware execution profiles — hold / trail / partial / cooldown (v6.3).

Never loosens quality floors or raises risk. High-vol and ranging/compression
regimes tighten behaviour; strong trends may allow holds up to the 2-15m
target window within absolute max.
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
    cooldown_scale: Decimal
    target_hold_min_minutes: int
    target_hold_max_minutes: int
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
            "cooldown_scale": str(self.cooldown_scale),
            "target_hold_min_minutes": self.target_hold_min_minutes,
            "target_hold_max_minutes": self.target_hold_max_minutes,
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
    cooldown_scale = Decimal("1.0")
    hold_lo = cfg.typical_hold_min_minutes
    hold_hi = cfg.typical_hold_max_minutes

    regime = assessment.regime

    if vol == "high":
        min_rr = max(min_rr, cfg.min_expected_rr + Decimal("0.2"))
        trail_after = max(trail_after, cfg.trail_after_r)
        abs_hold = max(cfg.typical_hold_max_minutes, min(abs_hold, 15))
        time_stop = min(time_stop, max(5, abs_hold // 2))
        trail_scale = Decimal("1.35")
        partial_at = min(partial_at, Decimal("0.8"))
        cooldown_scale = Decimal("1.25")
        hold_hi = min(hold_hi, 10)
        reasons.append("High vol → shorter hold, wider trail, higher RR floor")
    elif vol == "low":
        abs_hold = min(abs_hold, cfg.typical_hold_max_minutes)
        time_stop = min(time_stop, cfg.typical_hold_max_minutes)
        trail_after = min(trail_after, Decimal("0.8"))
        trail_scale = Decimal("0.85")
        cooldown_scale = Decimal("1.35")
        hold_hi = min(hold_hi, 8)
        reasons.append("Low vol → early trail, capped hold")

    if regime in {"range", "compression"}:
        min_rr = max(min_rr, cfg.min_expected_rr + Decimal("0.1"))
        abs_hold = min(abs_hold, max(8, cfg.typical_hold_min_minutes + 6))
        partial_enabled = True
        partial_pct = max(partial_pct, Decimal("50"))
        trail_after = min(trail_after, Decimal("0.8"))
        cooldown_scale = max(cooldown_scale, Decimal("1.25"))
        hold_hi = min(hold_hi, 8)
        reasons.append(f"{regime} → faster scale-out, tighter hold, longer cooldown")
    elif regime in {"strong_trend", "breakout"}:
        abs_hold = min(
            cfg.absolute_max_hold_minutes,
            max(abs_hold, cfg.typical_hold_max_minutes),
        )
        if vol != "high":
            trail_after = max(trail_after, cfg.trail_after_r)
            hold_hi = min(cfg.typical_hold_max_minutes, max(hold_hi, 12))
            cooldown_scale = min(cooldown_scale, Decimal("0.85"))
        reasons.append(f"{regime} → structure trail preferred, hold within 2-15m")
    elif regime == "expansion":
        min_rr = max(min_rr, cfg.min_expected_rr + Decimal("0.15"))
        abs_hold = min(abs_hold, 12)
        time_stop = min(time_stop, 8)
        trail_scale = max(trail_scale, Decimal("1.2"))
        cooldown_scale = max(cooldown_scale, Decimal("1.15"))
        hold_hi = min(hold_hi, 10)
        reasons.append("Expansion → protect with wider trail, capped hold")
    elif regime == "weak_trend":
        abs_hold = min(abs_hold, 12)
        partial_enabled = True
        partial_at = min(partial_at, Decimal("0.9"))
        hold_hi = min(hold_hi, 10)
        cooldown_scale = max(cooldown_scale, Decimal("1.05"))
        reasons.append("Weak trend → earlier partial, moderate hold")

    # Hard safety clamps
    if min_rr < cfg.min_expected_rr:
        min_rr = cfg.min_expected_rr
    if abs_hold > cfg.absolute_max_hold_minutes:
        abs_hold = cfg.absolute_max_hold_minutes
    if abs_hold < cfg.typical_hold_min_minutes:
        abs_hold = cfg.typical_hold_min_minutes
    if time_stop > abs_hold:
        time_stop = abs_hold
    hold_lo = max(cfg.typical_hold_min_minutes, min(hold_lo, hold_hi))
    hold_hi = min(hold_hi, cfg.typical_hold_max_minutes, abs_hold)

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
        cooldown_scale=cooldown_scale,
        target_hold_min_minutes=hold_lo,
        target_hold_max_minutes=hold_hi,
        reasons=tuple(reasons),
    )
