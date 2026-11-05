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


def _cost_price_units(
    *,
    money: Decimal | None,
    contract_size: Decimal | None,
    volume: Decimal | None,
) -> Decimal | None:
    """Convert a money cost to price units. None when conversion is impossible."""
    if money is None or contract_size is None or volume is None:
        return None
    per = Decimal(str(contract_size)) * Decimal(str(volume))
    if per <= 0:
        return None
    px = Decimal(str(money)) / per
    return abs(px) if px != 0 else Decimal("0")


def net_break_even_stop(
    position: ManagedPosition,
    config: PositionManagementConfig,
    *,
    spread: Decimal | None = None,
    commission: Decimal | None = None,
    swap: Decimal | None = None,
    contract_size: Decimal | None = None,
) -> tuple[Decimal | None, str]:
    """Cost-aware BE stop, or (None, reason) when costs are incomplete.

    Does not guess missing commission/swap/contract_size. Geometric offset_R is
    the floor; known costs push the stop further into profit.
    """
    geometric = break_even_stop(position, config)
    known_cost = Decimal("0")
    missing: list[str] = []
    # Spread: half-spread is a conservative round-trip proxy when provided.
    if spread is None:
        missing.append("spread")
    else:
        known_cost += max(Decimal(str(spread)), Decimal("0")) / Decimal("2")
    fee = _cost_price_units(
        money=commission,
        contract_size=contract_size,
        volume=position.remaining_volume or position.initial_volume,
    )
    if commission is not None and fee is None:
        missing.append("commission_unconvertible")
    elif commission is None:
        missing.append("commission")
    else:
        known_cost += fee or Decimal("0")
    sw = _cost_price_units(
        money=swap,
        contract_size=contract_size,
        volume=position.remaining_volume or position.initial_volume,
    )
    if swap is not None and sw is None:
        missing.append("swap_unconvertible")
    elif swap is None:
        missing.append("swap")
    else:
        known_cost += sw or Decimal("0")
    if missing:
        return None, "incomplete_costs:" + ",".join(missing)
    if position.side.lower() == "buy":
        return (geometric + known_cost).quantize(Decimal("0.01")), "net_be"
    return (geometric - known_cost).quantize(Decimal("0.01")), "net_be"


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
