"""BreakerDetector — detect OB invalidation into breaker blocks.

Why it exists
-------------
When price closes through an active/mitigated OB against its bias, the block
becomes a breaker. Structural fact only — not a signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.domain.market_data.candle import Candle
from app.domain.order_block.enums import OrderBlockSide, OrderBlockState
from app.domain.order_block.ids import breaker_id
from app.domain.order_block.models import BreakerBlock, OrderBlock
from app.domain.value_objects.market import Price


@dataclass(frozen=True, slots=True)
class BreakerDetectionResult:
    """Updated blocks plus newly formed breakers."""

    blocks: tuple[OrderBlock, ...]
    breakers: tuple[BreakerBlock, ...]


@dataclass(frozen=True, slots=True)
class BreakerDetector:
    """Detect close-through invalidation of active/mitigated order blocks."""

    def detect(
        self,
        blocks: Sequence[OrderBlock],
        candles: Sequence[Candle],
    ) -> BreakerDetectionResult:
        updated: list[OrderBlock] = []
        breakers: list[BreakerBlock] = []

        for block in blocks:
            if block.state not in {
                OrderBlockState.ACTIVE,
                OrderBlockState.MITIGATED,
            }:
                updated.append(block)
                continue

            event = self._find_break(block, candles)
            if event is None:
                updated.append(block)
                continue

            broken = block.transition(OrderBlockState.BREAKER)
            updated.append(broken)
            breakers.append(
                BreakerBlock(
                    symbol_code=broken.symbol_code,
                    timeframe=broken.timeframe,
                    order_block=broken,
                    broken_at=event[0],
                    break_price=event[1],
                    bar_index=event[2],
                    id=breaker_id(broken.id, event[2]),
                )
            )

        return BreakerDetectionResult(
            blocks=tuple(updated),
            breakers=tuple(breakers),
        )

    def _find_break(
        self,
        block: OrderBlock,
        candles: Sequence[Candle],
    ) -> tuple[datetime, Price, int] | None:
        for i in range(block.displacement_bar_index + 1, len(candles)):
            candle = candles[i]
            close = candle.close
            if block.side == OrderBlockSide.BULLISH:
                if close.value < block.zone.low_price.value:
                    return (candle.close_time, close, i)
            elif close.value > block.zone.high_price.value:
                return (candle.close_time, close, i)
        return None
