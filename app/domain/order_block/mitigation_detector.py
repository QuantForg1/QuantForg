"""MitigationDetector — detect price revisits into OB zones.

Why it exists
-------------
Tracks partial/full mitigation of active order blocks for lifecycle updates.
Not a trade signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.market_data.candle import Candle
from app.domain.order_block.enums import MitigationKind, OrderBlockState
from app.domain.order_block.ids import mitigation_id
from app.domain.order_block.models import MitigationBlock, OrderBlock
from app.domain.value_objects.market import Price


@dataclass(frozen=True, slots=True)
class MitigationDetectionResult:
    """Updated blocks plus mitigation records."""

    blocks: tuple[OrderBlock, ...]
    mitigations: tuple[MitigationBlock, ...]


@dataclass(frozen=True, slots=True)
class MitigationDetector:
    """Detect overlaps between later candles and active OB zones."""

    full_penetration: Decimal = Decimal("0.5")

    def detect(
        self,
        blocks: Sequence[OrderBlock],
        candles: Sequence[Candle],
    ) -> MitigationDetectionResult:
        updated: list[OrderBlock] = []
        mitigations: list[MitigationBlock] = []

        for block in blocks:
            if block.state != OrderBlockState.ACTIVE:
                updated.append(block)
                continue

            hit = self._find_mitigation(block, candles)
            if hit is None:
                updated.append(block)
                continue

            kind, when, price, index = hit
            mitigated = block.transition(OrderBlockState.MITIGATED)
            updated.append(mitigated)
            mitigations.append(
                MitigationBlock(
                    symbol_code=mitigated.symbol_code,
                    timeframe=mitigated.timeframe,
                    order_block=mitigated,
                    kind=kind,
                    mitigated_at=when,
                    touch_price=price,
                    bar_index=index,
                    id=mitigation_id(block.id, index, kind.value),
                )
            )

        return MitigationDetectionResult(
            blocks=tuple(updated),
            mitigations=tuple(mitigations),
        )

    def _find_mitigation(
        self,
        block: OrderBlock,
        candles: Sequence[Candle],
    ) -> tuple[MitigationKind, datetime, Price, int] | None:
        zone = block.zone
        zone_range = zone.range_size
        for i in range(block.displacement_bar_index + 1, len(candles)):
            candle = candles[i]
            if not zone.overlaps_candle(candle.low, candle.high):
                continue

            # Penetration depth relative to zone range.
            overlap_low = max(zone.low_price.value, candle.low.value)
            overlap_high = min(zone.high_price.value, candle.high.value)
            overlap = overlap_high - overlap_low
            kind = MitigationKind.PARTIAL
            if (
                zone_range > 0 and (overlap / zone_range) >= self.full_penetration
            ) or zone.contains(candle.close):
                kind = MitigationKind.FULL

            touch = (
                candle.low if candle.low.value >= zone.low_price.value else candle.high
            )
            if zone.contains(candle.close):
                touch = candle.close
            return (kind, candle.close_time, touch, i)
        return None
