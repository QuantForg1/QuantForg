"""GapQualityEvaluator — compute quality metrics for FVGs.

Why it exists
-------------
Produces :class:`GapQuality` from gap size, freshness, fill status, and
optional order-block confluence. Descriptive only — not a trade signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.fair_value_gap.enums import FairValueGapState, QualityGrade
from app.domain.fair_value_gap.models import FairValueGap, GapQuality
from app.domain.market_data.candle import Candle
from app.domain.order_block.models import OrderBlockSnapshot


@dataclass(frozen=True, slots=True)
class GapQualityEvaluator:
    """Evaluate structural quality of fair value gaps."""

    def evaluate(
        self,
        gaps: Sequence[FairValueGap],
        candles: Sequence[Candle],
        *,
        order_blocks: OrderBlockSnapshot | None = None,
        as_of_bar: int | None = None,
    ) -> tuple[FairValueGap, ...]:
        last_bar = as_of_bar if as_of_bar is not None else max(len(candles) - 1, 0)
        return tuple(
            gap.with_quality(self._quality_for(gap, candles, order_blocks, last_bar))
            for gap in gaps
        )

    def _quality_for(
        self,
        gap: FairValueGap,
        candles: Sequence[Candle],
        order_blocks: OrderBlockSnapshot | None,
        last_bar: int,
    ) -> GapQuality:
        mid = candles[gap.middle_bar_index]
        mid_range = mid.high.value - mid.low.value
        size_ratio = gap.zone.size / mid_range if mid_range > 0 else Decimal("0")
        freshness = max(last_bar - gap.middle_bar_index, 0)
        unfilled = gap.state not in {
            FairValueGapState.FILLED,
            FairValueGapState.INVALIDATED,
            FairValueGapState.EXPIRED,
        }
        confluence = self._ob_confluence(gap, order_blocks)

        score = Decimal("35")
        score += min(size_ratio * Decimal("25"), Decimal("30"))
        if freshness <= 15:
            score += Decimal("20")
        elif freshness <= 40:
            score += Decimal("10")
        if unfilled:
            score += Decimal("10")
        if confluence:
            score += Decimal("10")
        if score > Decimal("100"):
            score = Decimal("100")
        score = score.quantize(Decimal("0.01"))

        return GapQuality(
            score=score,
            grade=self._grade(score),
            size_ratio=size_ratio.quantize(Decimal("0.0001")),
            freshness_bars=freshness,
            order_block_confluence=confluence,
            unfilled=unfilled,
        )

    @staticmethod
    def _grade(score: Decimal) -> QualityGrade:
        if score >= Decimal("80"):
            return QualityGrade.A
        if score >= Decimal("65"):
            return QualityGrade.B
        if score >= Decimal("45"):
            return QualityGrade.C
        return QualityGrade.D

    @staticmethod
    def _ob_confluence(
        gap: FairValueGap,
        order_blocks: OrderBlockSnapshot | None,
    ) -> bool:
        if order_blocks is None:
            return False
        zone = gap.zone
        for block in order_blocks.order_blocks:
            ob_zone = block.zone
            # Overlapping price bands count as confluence.
            if not (
                ob_zone.high_price.value < zone.low_price.value
                or ob_zone.low_price.value > zone.high_price.value
            ):
                return True
        return False
