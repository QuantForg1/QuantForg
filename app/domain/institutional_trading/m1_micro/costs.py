"""Cost gate. A setup is rejected when the structural target does not clear it."""

from __future__ import annotations

from decimal import Decimal

_CENT = Decimal("0.01")


def round_trip_cost(
    *,
    spread: Decimal,
    slippage_points: Decimal = Decimal("0"),
    commission_points: Decimal = Decimal("0"),
) -> Decimal:
    """Points paid to enter and exit. Spread is paid once on a round trip."""
    spr = Decimal(str(spread or 0))
    if spr < 0:
        spr = Decimal("0")
    slip = Decimal(str(slippage_points or 0))
    comm = Decimal(str(commission_points or 0))
    return (spr + (slip * 2) + (comm * 2)).quantize(_CENT)


def cost_cleared(*, target_distance: Decimal, cost: Decimal, multiple: Decimal) -> bool:
    """True when the structural target is at least ``multiple`` times the cost.

    This is a minimum clearance check, not a forecast of profit.
    """
    dist = Decimal(str(target_distance or 0))
    paid = Decimal(str(cost or 0))
    mult = Decimal(str(multiple or 0))
    if dist <= 0 or paid < 0 or mult <= 0:
        return False
    return dist >= (paid * mult)
