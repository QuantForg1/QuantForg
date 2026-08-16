"""Canonical operational regime vocabulary — map only, no detector rewrite."""

from __future__ import annotations

from enum import Enum
from typing import Any


class OperationalRegime(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    BREAKOUT = "BREAKOUT"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    TRANSITION = "TRANSITION"
    LIQUIDITY_STRESS = "LIQUIDITY_STRESS"


_SCALPING_MAP: dict[str, OperationalRegime] = {
    "strong_trend": OperationalRegime.TRENDING,
    "weak_trend": OperationalRegime.TRENDING,
    "range": OperationalRegime.RANGING,
    "breakout": OperationalRegime.BREAKOUT,
    "expansion": OperationalRegime.HIGH_VOLATILITY,
    "compression": OperationalRegime.LOW_VOLATILITY,
    "high": OperationalRegime.HIGH_VOLATILITY,
    "low": OperationalRegime.LOW_VOLATILITY,
    "normal": OperationalRegime.TRANSITION,
}


def map_to_operational_regime(raw: str | None) -> tuple[OperationalRegime, str]:
    """Map existing labels → canonical. Unknown → TRANSITION + note."""
    key = str(raw or "").strip().lower()
    if not key:
        return OperationalRegime.TRANSITION, "UNKNOWN_REASON"
    if key in {m.value.lower() for m in OperationalRegime}:
        return OperationalRegime(key.upper()), "canonical"
    if key in _SCALPING_MAP:
        return _SCALPING_MAP[key], f"mapped_from:{key}"
    if "stress" in key or "illiquid" in key:
        return OperationalRegime.LIQUIDITY_STRESS, f"mapped_from:{key}"
    if "trend" in key:
        return OperationalRegime.TRENDING, f"mapped_from:{key}"
    if "range" in key or "mean" in key:
        return OperationalRegime.RANGING, f"mapped_from:{key}"
    if "break" in key:
        return OperationalRegime.BREAKOUT, f"mapped_from:{key}"
    return OperationalRegime.TRANSITION, f"unmapped:{key}"


def regime_align_snapshot(raw_regime: str | None = None) -> dict[str, Any]:
    op, note = map_to_operational_regime(raw_regime)
    return {
        "operational_regime": op.value,
        "source_regime": raw_regime,
        "mapping_note": note,
        "weights_live_change": False,
        "mode": "OBSERVE_MEASURE_SHADOW_RANK_VALIDATE",
    }
