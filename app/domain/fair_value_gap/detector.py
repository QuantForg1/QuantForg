"""FairValueGapDetector — three-candle imbalance detection.

Why it exists
-------------
Identifies bullish/bearish fair value gaps from OHLC series. Structural
observation only — not a trade signal or classic indicator.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.fair_value_gap.enums import FairValueGapSide, FairValueGapState
from app.domain.fair_value_gap.ids import fvg_id, zone_id
from app.domain.fair_value_gap.models import (
    FairValueGap,
    FairValueGapZone,
    GapLifecycle,
)
from app.domain.market_data.candle import Candle
from app.domain.market_structure.models import StructureSnapshot
from app.domain.value_objects.market import Price


@dataclass(frozen=True, slots=True)
class FairValueGapDetector:
    """Detect FVGs: gap between candle[i-2] and candle[i] around middle bar."""

    activate_immediately: bool = True

    def detect(
        self,
        candles: Sequence[Candle],
        structure: StructureSnapshot | None = None,
    ) -> tuple[FairValueGap, ...]:
        """Return newly detected gaps (ACTIVE or DETECTED).

        ``structure`` is accepted for pipeline compatibility; detection is
        candle-geometric and does not require BOS/CHoCH.
        """
        _ = structure  # optional context reserved for future filters
        if len(candles) < 3:
            return ()

        gaps: list[FairValueGap] = []
        for i in range(2, len(candles)):
            left = candles[i - 2]
            mid = candles[i - 1]
            right = candles[i]
            bullish = self._bullish_gap(left, mid, right, i - 1)
            if bullish is not None:
                gaps.append(bullish)
                continue
            bearish = self._bearish_gap(left, mid, right, i - 1)
            if bearish is not None:
                gaps.append(bearish)
        return tuple(gaps)

    def _bullish_gap(
        self,
        left: Candle,
        mid: Candle,
        right: Candle,
        middle_index: int,
    ) -> FairValueGap | None:
        # Bullish FVG: right.low > left.high (gap up / buy-side imbalance)
        if right.low.value <= left.high.value:
            return None
        # Prefer impulsive middle (up-close); still allow if geometric gap holds.
        low = left.high
        high = right.low
        return self._build(
            mid=mid,
            right=right,
            middle_index=middle_index,
            side=FairValueGapSide.BULLISH,
            low=low,
            high=high,
        )

    def _bearish_gap(
        self,
        left: Candle,
        mid: Candle,
        right: Candle,
        middle_index: int,
    ) -> FairValueGap | None:
        # Bearish FVG: right.high < left.low (gap down / sell-side imbalance)
        if right.high.value >= left.low.value:
            return None
        low = right.high
        high = left.low
        return self._build(
            mid=mid,
            right=right,
            middle_index=middle_index,
            side=FairValueGapSide.BEARISH,
            low=low,
            high=high,
        )

    def _build(
        self,
        *,
        mid: Candle,
        right: Candle,
        middle_index: int,
        side: FairValueGapSide,
        low: Price,
        high: Price,
    ) -> FairValueGap:
        symbol = mid.symbol_code
        tf = mid.timeframe
        formed_at = right.close_time
        zone = FairValueGapZone(
            symbol_code=symbol,
            timeframe=tf,
            low_price=low,
            high_price=high,
            middle_bar_index=middle_index,
            formed_at=formed_at,
            id=zone_id(
                str(symbol),
                tf.value,
                middle_index,
                str(low),
                str(high),
            ),
        )
        state = (
            FairValueGapState.ACTIVE
            if self.activate_immediately
            else FairValueGapState.DETECTED
        )
        lifecycle = GapLifecycle(
            state=FairValueGapState.DETECTED,
            detected_at=formed_at,
            updated_at=formed_at,
        )
        if state == FairValueGapState.ACTIVE:
            lifecycle = lifecycle.transition(FairValueGapState.ACTIVE, at=formed_at)

        return FairValueGap(
            symbol_code=symbol,
            timeframe=tf,
            side=side,
            zone=zone,
            lifecycle=lifecycle,
            left_bar_index=middle_index - 1,
            middle_bar_index=middle_index,
            right_bar_index=middle_index + 1,
            id=fvg_id(
                str(symbol),
                tf.value,
                side.value,
                middle_index,
                str(low),
                str(high),
            ),
        )
