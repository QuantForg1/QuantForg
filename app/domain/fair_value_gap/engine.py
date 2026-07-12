"""FairValueGapEngine — orchestrate detect → fill → invalidate → quality → snapshot.

Why it exists
-------------
Single entry point that loads price/structure/order-block context, lifecycles
fair value gaps, and returns an immutable :class:`FairValueGapSnapshot` plus
domain events. Does not trade, call MetaTrader, run AI, or emit signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.events.base import DomainEvent
from app.domain.events.fair_value_gap import (
    FairValueGapDetected,
    FairValueGapExpired,
    FairValueGapStateChanged,
    GapFilled,
    GapInvalidated,
    GapPartiallyFilled,
)
from app.domain.fair_value_gap.detector import FairValueGapDetector
from app.domain.fair_value_gap.enums import FairValueGapState, FillKind
from app.domain.fair_value_gap.fill_detector import GapFillDetector
from app.domain.fair_value_gap.invalidation_detector import (
    GapInvalidationDetector,
    InvalidationEvent,
)
from app.domain.fair_value_gap.models import FairValueGap, FairValueGapSnapshot, GapFill
from app.domain.fair_value_gap.quality_evaluator import GapQualityEvaluator
from app.domain.interfaces.fair_value_gap import (
    FairValueGapRepositoryPort,
    MarketStructurePort,
    OrderBlockSnapshotPort,
    PriceHistoryPort,
)
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode


@dataclass(frozen=True, slots=True)
class FairValueGapResult:
    """Engine output: immutable snapshot plus pending domain events."""

    snapshot: FairValueGapSnapshot
    events: tuple[DomainEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class FairValueGapEngine:
    """Orchestrate fair-value-gap analysis for one symbol/timeframe."""

    prices: PriceHistoryPort
    structure: MarketStructurePort | None = None
    order_blocks: OrderBlockSnapshotPort | None = None
    repository: FairValueGapRepositoryPort | None = None
    detector: FairValueGapDetector = field(default_factory=FairValueGapDetector)
    fills: GapFillDetector = field(default_factory=GapFillDetector)
    invalidations: GapInvalidationDetector = field(
        default_factory=GapInvalidationDetector
    )
    quality: GapQualityEvaluator = field(default_factory=GapQualityEvaluator)
    max_age_bars: int = 100
    candle_limit: int = 500

    async def analyze(
        self,
        symbol_code: str | SymbolCode,
        timeframe: Timeframe | str,
        *,
        persist: bool = False,
        as_of: datetime | None = None,
    ) -> FairValueGapResult:
        """Run a full FVG analysis pass and return snapshot + events."""
        code = (
            symbol_code
            if isinstance(symbol_code, SymbolCode)
            else SymbolCode(value=symbol_code)
        )
        tf = (
            timeframe
            if isinstance(timeframe, Timeframe)
            else Timeframe.parse(timeframe)
        )
        moment = as_of or datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)

        candles = await self.prices.get_candles(code, tf, limit=self.candle_limit)
        structure = None
        if self.structure is not None:
            structure = await self.structure.get_latest_snapshot(code, tf)
        ob_snap = None
        if self.order_blocks is not None:
            ob_snap = await self.order_blocks.get_latest_snapshot(code, tf)

        previous: FairValueGapSnapshot | None = None
        if self.repository is not None:
            previous = await self.repository.get_latest_snapshot(code, tf)

        detected = self.detector.detect(candles, structure)
        prior_live: tuple[FairValueGap, ...] = ()
        if previous is not None:
            terminal = {
                FairValueGapState.EXPIRED,
                FairValueGapState.FILLED,
                FairValueGapState.INVALIDATED,
            }
            detected_ids = {g.id for g in detected}
            prior_live = tuple(
                g
                for g in previous.gaps
                if g.state not in terminal and g.id not in detected_ids
            )

        candidates = prior_live + detected
        fill_result = self.fills.detect(candidates, candles)
        inv_result = self.invalidations.detect(fill_result.gaps, candles)
        gaps = self._expire_stale(inv_result.gaps, len(candles), moment)
        gaps = self.quality.evaluate(gaps, candles, order_blocks=ob_snap)

        prior_fills = previous.fills if previous else ()
        fills = self._merge_by_id(prior_fills, fill_result.fills)

        snapshot = FairValueGapSnapshot(
            symbol_code=code,
            timeframe=tf,
            as_of=moment,
            gaps=gaps,
            fills=fills,
        )
        events = self._build_events(
            snapshot,
            previous,
            detected,
            fill_result.fills,
            inv_result.invalidations,
        )

        if persist and self.repository is not None:
            await self.repository.save_snapshot(snapshot)

        return FairValueGapResult(snapshot=snapshot, events=tuple(events))

    def _expire_stale(
        self,
        gaps: tuple[FairValueGap, ...],
        series_length: int,
        as_of: datetime,
    ) -> tuple[FairValueGap, ...]:
        last_index = max(series_length - 1, 0)
        result: list[FairValueGap] = []
        for gap in gaps:
            if gap.state in {
                FairValueGapState.EXPIRED,
                FairValueGapState.FILLED,
                FairValueGapState.INVALIDATED,
            }:
                result.append(gap)
                continue
            age = last_index - gap.middle_bar_index
            if age > self.max_age_bars:
                result.append(gap.transition(FairValueGapState.EXPIRED, at=as_of))
            else:
                result.append(gap)
        return tuple(result)

    @staticmethod
    def _merge_by_id(
        prior: tuple[GapFill, ...],
        fresh: tuple[GapFill, ...],
    ) -> tuple[GapFill, ...]:
        by_id = {item.id: item for item in prior}
        for item in fresh:
            by_id[item.id] = item
        return tuple(by_id.values())

    def _build_events(
        self,
        snapshot: FairValueGapSnapshot,
        previous: FairValueGapSnapshot | None,
        newly_detected: tuple[FairValueGap, ...],
        new_fills: tuple[GapFill, ...],
        invalidations: tuple[InvalidationEvent, ...],
    ) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        prev_map = {g.id: g for g in previous.gaps} if previous else {}
        prev_fill_ids = {f.id for f in previous.fills} if previous else set()
        detected_ids = {g.id for g in newly_detected}

        for gap in snapshot.gaps:
            prev = prev_map.get(gap.id)
            if gap.id in detected_ids and prev is None:
                events.append(
                    FairValueGapDetected(
                        gap_id=gap.id,
                        symbol_code=str(gap.symbol_code),
                        timeframe=gap.timeframe.value,
                        side=gap.side.value,
                        state=gap.state.value,
                        low_price=str(gap.zone.low_price),
                        high_price=str(gap.zone.high_price),
                        occurred_at=gap.lifecycle.detected_at,
                    )
                )

            if prev is None or prev.state != gap.state:
                events.append(
                    FairValueGapStateChanged(
                        gap_id=gap.id,
                        symbol_code=str(gap.symbol_code),
                        timeframe=gap.timeframe.value,
                        previous_state=(
                            prev.state.value if prev is not None else "none"
                        ),
                        current_state=gap.state.value,
                        occurred_at=snapshot.as_of,
                    )
                )

            if gap.state == FairValueGapState.EXPIRED and (
                prev is None or prev.state != FairValueGapState.EXPIRED
            ):
                events.append(
                    FairValueGapExpired(
                        gap_id=gap.id,
                        symbol_code=str(gap.symbol_code),
                        timeframe=gap.timeframe.value,
                        previous_state=(
                            prev.state.value if prev is not None else "detected"
                        ),
                        occurred_at=snapshot.as_of,
                    )
                )

        for fill in new_fills:
            if fill.id in prev_fill_ids:
                continue
            if fill.kind == FillKind.FULL:
                events.append(
                    GapFilled(
                        fill_id=fill.id,
                        gap_id=fill.gap.id,
                        symbol_code=str(fill.symbol_code),
                        timeframe=fill.timeframe.value,
                        fill_price=str(fill.fill_price),
                        occurred_at=fill.filled_at,
                    )
                )
            else:
                events.append(
                    GapPartiallyFilled(
                        fill_id=fill.id,
                        gap_id=fill.gap.id,
                        symbol_code=str(fill.symbol_code),
                        timeframe=fill.timeframe.value,
                        fill_ratio=str(fill.fill_ratio),
                        fill_price=str(fill.fill_price),
                        occurred_at=fill.filled_at,
                    )
                )

        for inv in invalidations:
            events.append(
                GapInvalidated(
                    gap_id=inv.gap.id,
                    symbol_code=str(inv.gap.symbol_code),
                    timeframe=inv.gap.timeframe.value,
                    invalidate_price=str(inv.invalidate_price),
                    previous_state=inv.previous_state.value,
                    occurred_at=inv.invalidated_at,
                )
            )

        return events
