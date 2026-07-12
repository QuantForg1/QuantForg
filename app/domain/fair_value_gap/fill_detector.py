"""GapFillDetector — detect partial/full fills of active FVGs.

Why it exists
-------------
Tracks how deeply later price action re-enters the gap zone. Structural
fact only — not a trade signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.fair_value_gap.enums import (
    FairValueGapSide,
    FairValueGapState,
    FillKind,
)
from app.domain.fair_value_gap.ids import fill_id
from app.domain.fair_value_gap.models import FairValueGap, GapFill, GapLifecycle
from app.domain.market_data.candle import Candle
from app.domain.value_objects.market import Price


@dataclass(frozen=True, slots=True)
class GapFillResult:
    """Updated gaps plus fill records from this pass."""

    gaps: tuple[FairValueGap, ...]
    fills: tuple[GapFill, ...]


@dataclass(frozen=True, slots=True)
class GapFillDetector:
    """Detect overlaps that fill bullish/bearish FVG zones."""

    full_ratio: Decimal = Decimal("0.99")

    def detect(
        self,
        gaps: Sequence[FairValueGap],
        candles: Sequence[Candle],
    ) -> GapFillResult:
        updated: list[FairValueGap] = []
        fills: list[GapFill] = []

        for gap in gaps:
            if gap.state not in {
                FairValueGapState.ACTIVE,
                FairValueGapState.PARTIALLY_FILLED,
            }:
                updated.append(gap)
                continue

            hit = self._best_fill(gap, candles)
            if hit is None:
                updated.append(gap)
                continue

            kind, ratio, price, index, when = hit
            new_gap = self._apply_fill(gap, kind=kind, ratio=ratio, at=when)
            updated.append(new_gap)
            fills.append(
                GapFill(
                    symbol_code=new_gap.symbol_code,
                    timeframe=new_gap.timeframe,
                    gap=new_gap,
                    kind=kind,
                    fill_ratio=ratio,
                    fill_price=price,
                    bar_index=index,
                    filled_at=when,
                    id=fill_id(gap.id, index, kind.value),
                )
            )

        return GapFillResult(gaps=tuple(updated), fills=tuple(fills))

    def _apply_fill(
        self,
        gap: FairValueGap,
        *,
        kind: FillKind,
        ratio: Decimal,
        at: datetime,
    ) -> FairValueGap:
        if kind == FillKind.FULL:
            if gap.state == FairValueGapState.PARTIALLY_FILLED:
                return gap.transition(
                    FairValueGapState.FILLED, at=at, fill_ratio=Decimal("1")
                )
            return gap.transition(
                FairValueGapState.FILLED, at=at, fill_ratio=Decimal("1")
            )

        if gap.state == FairValueGapState.ACTIVE:
            return gap.transition(
                FairValueGapState.PARTIALLY_FILLED, at=at, fill_ratio=ratio
            )

        # Already partially filled — deepen ratio without illegal same-state hop.
        lc = gap.lifecycle
        deeper = max(lc.fill_ratio, ratio)
        refreshed = GapLifecycle(
            state=FairValueGapState.PARTIALLY_FILLED,
            detected_at=lc.detected_at,
            updated_at=at,
            fill_ratio=deeper,
            activated_at=lc.activated_at,
            filled_at=lc.filled_at,
            invalidated_at=lc.invalidated_at,
            expired_at=lc.expired_at,
        )
        return gap.with_lifecycle(refreshed)

    def _best_fill(
        self,
        gap: FairValueGap,
        candles: Sequence[Candle],
    ) -> tuple[FillKind, Decimal, Price, int, datetime] | None:
        zone = gap.zone
        best: tuple[FillKind, Decimal, Price, int, datetime] | None = None

        for i in range(gap.right_bar_index + 1, len(candles)):
            candle = candles[i]
            if not zone.overlaps_candle(candle.low, candle.high):
                continue

            ratio = self._fill_ratio(gap, candle)
            if ratio <= gap.lifecycle.fill_ratio:
                continue

            kind = FillKind.FULL if ratio >= self.full_ratio else FillKind.PARTIAL
            if kind == FillKind.FULL:
                ratio = Decimal("1")

            touch = candle.low if gap.side == FairValueGapSide.BULLISH else candle.high
            candidate = (kind, ratio, touch, i, candle.close_time)
            if best is None or candidate[1] > best[1]:
                best = candidate
            if kind == FillKind.FULL:
                return candidate
        return best

    def _fill_ratio(self, gap: FairValueGap, candle: Candle) -> Decimal:
        zone = gap.zone
        size = zone.size
        if size <= 0:
            return Decimal("0")

        if gap.side == FairValueGapSide.BULLISH:
            if candle.low.value >= zone.high_price.value:
                return Decimal("0")
            if candle.low.value <= zone.low_price.value:
                return Decimal("1")
            filled = zone.high_price.value - candle.low.value
        else:
            if candle.high.value <= zone.low_price.value:
                return Decimal("0")
            if candle.high.value >= zone.high_price.value:
                return Decimal("1")
            filled = candle.high.value - zone.low_price.value

        ratio = filled / size
        if ratio < 0:
            return Decimal("0")
        if ratio > 1:
            return Decimal("1")
        return ratio.quantize(Decimal("0.0001"))
