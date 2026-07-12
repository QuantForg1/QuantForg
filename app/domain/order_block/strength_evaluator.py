"""OrderBlockStrengthEvaluator — compute quality metrics for OBs.

Why it exists
-------------
Produces :class:`OrderBlockQuality` from displacement, freshness, mitigation
status, and optional liquidity confluence. Quality is descriptive — not a
signal score for entries.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.liquidity.models import LiquiditySnapshot
from app.domain.market_data.candle import Candle
from app.domain.order_block.enums import (
    OrderBlockSide,
    OrderBlockState,
    QualityGrade,
)
from app.domain.order_block.models import OrderBlock, OrderBlockQuality


@dataclass(frozen=True, slots=True)
class OrderBlockStrengthEvaluator:
    """Evaluate structural quality of order blocks."""

    def evaluate(
        self,
        blocks: Sequence[OrderBlock],
        candles: Sequence[Candle],
        *,
        liquidity: LiquiditySnapshot | None = None,
        as_of_bar: int | None = None,
    ) -> tuple[OrderBlock, ...]:
        """Return blocks with attached :class:`OrderBlockQuality`."""
        last_bar = as_of_bar if as_of_bar is not None else max(len(candles) - 1, 0)
        return tuple(
            block.with_quality(self._quality_for(block, candles, liquidity, last_bar))
            for block in blocks
        )

    def _quality_for(
        self,
        block: OrderBlock,
        candles: Sequence[Candle],
        liquidity: LiquiditySnapshot | None,
        last_bar: int,
    ) -> OrderBlockQuality:
        zone_range = block.zone.range_size or Decimal("1")
        disp = candles[block.displacement_bar_index]
        origin = candles[block.origin_bar_index]
        if block.side == OrderBlockSide.BULLISH:
            move = max(disp.close.value - origin.low.value, Decimal("0"))
        else:
            move = max(origin.high.value - disp.close.value, Decimal("0"))
        displacement_ratio = move / zone_range

        freshness = max(last_bar - block.origin_bar_index, 0)
        unmitigated = block.state not in {
            OrderBlockState.MITIGATED,
            OrderBlockState.BREAKER,
            OrderBlockState.EXPIRED,
        }
        confluence = self._liquidity_confluence(block, liquidity)

        score = Decimal("40")
        score += min(displacement_ratio * Decimal("15"), Decimal("30"))
        if freshness <= 20:
            score += Decimal("15")
        elif freshness <= 50:
            score += Decimal("8")
        if unmitigated:
            score += Decimal("10")
        if confluence:
            score += Decimal("10")
        if score > Decimal("100"):
            score = Decimal("100")
        score = score.quantize(Decimal("0.01"))

        return OrderBlockQuality(
            score=score,
            grade=self._grade(score),
            displacement_ratio=displacement_ratio.quantize(Decimal("0.0001")),
            freshness_bars=freshness,
            liquidity_confluence=confluence,
            unmitigated=unmitigated,
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
    def _liquidity_confluence(
        block: OrderBlock,
        liquidity: LiquiditySnapshot | None,
    ) -> bool:
        if liquidity is None:
            return False
        zone = block.zone
        for pool in liquidity.pools:
            if zone.contains(pool.price):
                return True
        for sweep in liquidity.sweeps:
            if zone.contains(sweep.sweep_price) or zone.contains(sweep.close_price):
                return True
        return False
