"""R-multiple and ATR regime helpers — pure deterministic math."""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

from app.domain.institutional_trading.management.config import PositionManagementConfig
from app.domain.institutional_trading.management.models import (
    ManagedPosition,
    VolatilityRegime,
)


def signed_r(position: ManagedPosition, price: Decimal) -> Decimal:
    """Current R multiple (positive = favorable)."""
    risk = position.risk_distance
    if risk <= 0:
        return Decimal("0")
    if position.side.lower() == "buy":
        return ((price - position.entry_price) / risk).quantize(Decimal("0.0001"))
    return ((position.entry_price - price) / risk).quantize(Decimal("0.0001"))


def volatility_regime(
    atr: Decimal,
    mid: Decimal,
    config: PositionManagementConfig,
) -> VolatilityRegime:
    if mid <= 0 or atr <= 0:
        return VolatilityRegime.NORMAL
    pct = (atr / mid * Decimal("100")).quantize(Decimal("0.01"))
    if pct >= config.atr_high_pct:
        return VolatilityRegime.HIGH
    if pct <= config.atr_low_pct:
        return VolatilityRegime.LOW
    return VolatilityRegime.NORMAL


def trail_distance(
    atr: Decimal,
    regime: VolatilityRegime,
    config: PositionManagementConfig,
) -> Decimal:
    if regime is VolatilityRegime.HIGH:
        mult = config.trail_atr_mult_high
    elif regime is VolatilityRegime.LOW:
        mult = config.trail_atr_mult_low
    else:
        mult = config.trail_atr_mult_normal
    return (atr * mult).quantize(Decimal("0.0001"))


def break_even_stop(
    position: ManagedPosition,
    config: PositionManagementConfig,
) -> Decimal:
    """Entry ± offset_R into profit. Never widens risk vs entry."""
    offset = position.risk_distance * config.break_even_offset_r
    if position.side.lower() == "buy":
        return (position.entry_price + offset).quantize(Decimal("0.01"))
    return (position.entry_price - offset).quantize(Decimal("0.01"))


def is_stop_improvement(
    position: ManagedPosition,
    new_stop: Decimal,
) -> bool:
    """True if new_stop never moves backwards (never widens risk)."""
    current = (
        position.current_stop if position.current_stop > 0 else position.initial_stop
    )
    if position.side.lower() == "buy":
        return new_stop > current
    return new_stop < current if current > 0 else True


def trail_stop_price(
    position: ManagedPosition,
    price: Decimal,
    distance: Decimal,
) -> Decimal:
    if position.side.lower() == "buy":
        return (price - distance).quantize(Decimal("0.01"))
    return (price + distance).quantize(Decimal("0.01"))


def partial_close_volume(
    position: ManagedPosition,
    config: PositionManagementConfig,
) -> Decimal:
    pct = config.partial_close_pct / Decimal("100")
    raw = (position.remaining_volume * pct).quantize(Decimal("0.01"))
    step = config.volume_step
    if step > 0:
        steps = (raw / step).to_integral_value(rounding=ROUND_DOWN)
        raw = steps * step
    if raw < config.min_volume:
        return Decimal("0")
    # Leave at least min_volume remaining when possible
    remain = position.remaining_volume - raw
    if remain > 0 and remain < config.min_volume:
        raw = position.remaining_volume - config.min_volume
        if raw < config.min_volume:
            return Decimal("0")
    return raw


def opposite_side(side: str) -> str:
    return "sell" if side.lower() == "buy" else "buy"
