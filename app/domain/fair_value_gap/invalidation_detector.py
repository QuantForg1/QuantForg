"""GapInvalidationDetector — invalidate FVGs on opposing close-through.

Why it exists
-------------
A bullish gap is invalidated when price closes below the gap low; a bearish
gap when price closes above the gap high (after formation). Structural fact
only — not a signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.domain.fair_value_gap.enums import FairValueGapSide, FairValueGapState
from app.domain.fair_value_gap.models import FairValueGap
from app.domain.market_data.candle import Candle
from app.domain.value_objects.market import Price


@dataclass(frozen=True, slots=True)
class InvalidationEvent:
    """One invalidation observation."""

    gap: FairValueGap
    previous_state: FairValueGapState
    invalidate_price: Price
    bar_index: int
    invalidated_at: datetime


@dataclass(frozen=True, slots=True)
class GapInvalidationResult:
    """Updated gaps plus invalidation events."""

    gaps: tuple[FairValueGap, ...]
    invalidations: tuple[InvalidationEvent, ...]


@dataclass(frozen=True, slots=True)
class GapInvalidationDetector:
    """Detect close-through invalidation of active / partially filled gaps."""

    def detect(
        self,
        gaps: Sequence[FairValueGap],
        candles: Sequence[Candle],
    ) -> GapInvalidationResult:
        updated: list[FairValueGap] = []
        events: list[InvalidationEvent] = []

        for gap in gaps:
            if gap.state not in {
                FairValueGapState.ACTIVE,
                FairValueGapState.PARTIALLY_FILLED,
            }:
                updated.append(gap)
                continue

            hit = self._find_invalidation(gap, candles)
            if hit is None:
                updated.append(gap)
                continue

            price, index, when = hit
            previous = gap.state
            invalidated = gap.transition(FairValueGapState.INVALIDATED, at=when)
            updated.append(invalidated)
            events.append(
                InvalidationEvent(
                    gap=invalidated,
                    previous_state=previous,
                    invalidate_price=price,
                    bar_index=index,
                    invalidated_at=when,
                )
            )

        return GapInvalidationResult(
            gaps=tuple(updated),
            invalidations=tuple(events),
        )

    def _find_invalidation(
        self,
        gap: FairValueGap,
        candles: Sequence[Candle],
    ) -> tuple[Price, int, datetime] | None:
        for i in range(gap.right_bar_index + 1, len(candles)):
            candle = candles[i]
            close = candle.close
            if gap.side == FairValueGapSide.BULLISH:
                if close.value < gap.zone.low_price.value:
                    return (close, i, candle.close_time)
            elif close.value > gap.zone.high_price.value:
                return (close, i, candle.close_time)
        return None
