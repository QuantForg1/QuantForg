"""OrderBlockValidator — promote DETECTED blocks through validation gates.

Why it exists
-------------
Filters structurally weak candidates before they become ACTIVE. Does not
generate trade signals.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.market_data.candle import Candle
from app.domain.order_block.enums import OrderBlockSide, OrderBlockState
from app.domain.order_block.models import OrderBlock


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Blocks that passed validation (VALIDATED then ACTIVE) vs expired."""

    activated: tuple[OrderBlock, ...]
    expired: tuple[OrderBlock, ...]


@dataclass(frozen=True, slots=True)
class OrderBlockValidator:
    """Validate detected order blocks against displacement and integrity rules."""

    min_displacement_ratio: Decimal = Decimal("1.5")
    activate_immediately: bool = True

    def validate(
        self,
        blocks: Sequence[OrderBlock],
        candles: Sequence[Candle],
        *,
        as_of: datetime | None = None,
    ) -> ValidationResult:
        """Transition DETECTED → VALIDATED → ACTIVE (or EXPIRED)."""
        activated: list[OrderBlock] = []
        expired: list[OrderBlock] = []

        for block in blocks:
            if block.state != OrderBlockState.DETECTED:
                activated.append(block)
                continue

            if not self._has_displacement(block, candles):
                expired.append(block.transition(OrderBlockState.EXPIRED, at=as_of))
                continue

            if self._already_invalidated(block, candles):
                expired.append(block.transition(OrderBlockState.EXPIRED, at=as_of))
                continue

            validated = block.transition(OrderBlockState.VALIDATED, at=as_of)
            if self.activate_immediately:
                validated = validated.transition(OrderBlockState.ACTIVE, at=as_of)
            activated.append(validated)

        return ValidationResult(
            activated=tuple(activated),
            expired=tuple(expired),
        )

    def _has_displacement(
        self,
        block: OrderBlock,
        candles: Sequence[Candle],
    ) -> bool:
        zone_range = block.zone.range_size
        if zone_range <= 0:
            return False
        disp = candles[block.displacement_bar_index]
        origin = candles[block.origin_bar_index]
        if block.side == OrderBlockSide.BULLISH:
            move = disp.close.value - origin.low.value
        else:
            move = origin.high.value - disp.close.value
        if move <= 0:
            return False
        return (move / zone_range) >= self.min_displacement_ratio

    def _already_invalidated(
        self,
        block: OrderBlock,
        candles: Sequence[Candle],
    ) -> bool:
        """True if a close already sliced through the zone against bias."""
        for i in range(block.displacement_bar_index + 1, len(candles)):
            close = candles[i].close.value
            if block.side == OrderBlockSide.BULLISH:
                if close < block.zone.low_price.value:
                    return True
            elif close > block.zone.high_price.value:
                return True
        return False
