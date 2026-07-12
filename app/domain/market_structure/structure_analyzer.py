"""StructureAnalyzer — classify HH/HL/LH/LL and detect BOS / CHoCH.

Why it exists
-------------
Turns an ordered swing sequence into structure nodes and detects Break of
Structure / Change of Character relative to the prevailing trend. Does not
generate entry/exit signals.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.market_data.candle import Candle
from app.domain.market_structure.enums import StructureRole, SwingKind, TrendDirection
from app.domain.market_structure.models import (
    BreakOfStructure,
    ChangeOfCharacter,
    StructureNode,
    SwingPoint,
)
from app.domain.value_objects.market import Price


@dataclass(frozen=True, slots=True)
class StructureAnalysisResult:
    """Immutable result of a structure analysis pass."""

    nodes: tuple[StructureNode, ...]
    breaks_of_structure: tuple[BreakOfStructure, ...]
    changes_of_character: tuple[ChangeOfCharacter, ...]


@dataclass(frozen=True, slots=True)
class StructureAnalyzer:
    """Analyse swing sequences into structure roles and break events."""

    def build_nodes(self, swings: Sequence[SwingPoint]) -> tuple[StructureNode, ...]:
        """Assign HH/HL/LH/LL roles by comparing successive same-kind swings."""
        if not swings:
            return ()

        last_high: SwingPoint | None = None
        last_low: SwingPoint | None = None
        nodes: list[StructureNode] = []

        for index, swing in enumerate(swings):
            role = StructureRole.UNKNOWN
            if swing.kind == SwingKind.HIGH:
                if last_high is None:
                    role = StructureRole.UNKNOWN
                elif swing.price.value > last_high.price.value:
                    role = StructureRole.HIGHER_HIGH
                elif swing.price.value < last_high.price.value:
                    role = StructureRole.LOWER_HIGH
                else:
                    role = StructureRole.EQUAL_HIGH
                last_high = swing
            else:
                if last_low is None:
                    role = StructureRole.UNKNOWN
                elif swing.price.value > last_low.price.value:
                    role = StructureRole.HIGHER_LOW
                elif swing.price.value < last_low.price.value:
                    role = StructureRole.LOWER_LOW
                else:
                    role = StructureRole.EQUAL_LOW
                last_low = swing

            nodes.append(StructureNode(swing=swing, role=role, sequence=index))

        return tuple(nodes)

    def detect_breaks(
        self,
        *,
        swings: Sequence[SwingPoint],
        candles: Sequence[Candle],
        trend: TrendDirection,
    ) -> StructureAnalysisResult:
        """Detect BOS / CHoCH using swing levels and subsequent bar closes.

        Rules (structural, not signals)
        -------------------------------
        - Uptrend BOS: close breaks above prior swing high.
        - Uptrend CHoCH: close breaks below prior swing low.
        - Downtrend BOS: close breaks below prior swing low.
        - Downtrend CHoCH: close breaks above prior swing high.
        - Range / unknown: no BOS/CHoCH emitted.
        """
        nodes = self.build_nodes(swings)
        if trend in {TrendDirection.RANGE, TrendDirection.UNKNOWN}:
            return StructureAnalysisResult(
                nodes=nodes,
                breaks_of_structure=(),
                changes_of_character=(),
            )

        bos_events: list[BreakOfStructure] = []
        choch_events: list[ChangeOfCharacter] = []

        highs = [s for s in swings if s.kind == SwingKind.HIGH]
        lows = [s for s in swings if s.kind == SwingKind.LOW]

        for candle in candles:
            close = candle.close
            ts = candle.close_time
            prior_high = self._last_swing_before(highs, candle)
            prior_low = self._last_swing_before(lows, candle)

            if trend == TrendDirection.UP:
                if prior_high is not None and close.value > prior_high.price.value:
                    bos_events.append(
                        self._bos(prior_high, close, ts, TrendDirection.UP)
                    )
                if prior_low is not None and close.value < prior_low.price.value:
                    choch_events.append(
                        self._choch(prior_low, close, ts, TrendDirection.UP)
                    )
            elif trend == TrendDirection.DOWN:
                if prior_low is not None and close.value < prior_low.price.value:
                    bos_events.append(
                        self._bos(prior_low, close, ts, TrendDirection.DOWN)
                    )
                if prior_high is not None and close.value > prior_high.price.value:
                    choch_events.append(
                        self._choch(prior_high, close, ts, TrendDirection.DOWN)
                    )

        return StructureAnalysisResult(
            nodes=nodes,
            breaks_of_structure=tuple(self._dedupe_bos(bos_events)),
            changes_of_character=tuple(self._dedupe_choch(choch_events)),
        )

    @staticmethod
    def _last_swing_before(
        swings: Sequence[SwingPoint],
        candle: Candle,
    ) -> SwingPoint | None:
        prior = [s for s in swings if s.timestamp <= candle.open_time]
        return prior[-1] if prior else None

    @staticmethod
    def _bos(
        swing: SwingPoint,
        price: Price,
        when: datetime,
        trend: TrendDirection,
    ) -> BreakOfStructure:
        return BreakOfStructure(
            symbol_code=swing.symbol_code,
            timeframe=swing.timeframe,
            broken_swing=swing,
            break_price=price,
            broken_at=when,
            trend_direction=trend,
        )

    @staticmethod
    def _choch(
        swing: SwingPoint,
        price: Price,
        when: datetime,
        previous_trend: TrendDirection,
    ) -> ChangeOfCharacter:
        return ChangeOfCharacter(
            symbol_code=swing.symbol_code,
            timeframe=swing.timeframe,
            broken_swing=swing,
            break_price=price,
            broken_at=when,
            previous_trend=previous_trend,
        )

    @staticmethod
    def _dedupe_bos(events: Sequence[BreakOfStructure]) -> list[BreakOfStructure]:
        seen: set[UUID] = set()
        result: list[BreakOfStructure] = []
        for event in events:
            key = event.broken_swing.id
            if key in seen:
                continue
            seen.add(key)
            result.append(event)
        return result

    @staticmethod
    def _dedupe_choch(
        events: Sequence[ChangeOfCharacter],
    ) -> list[ChangeOfCharacter]:
        seen: set[UUID] = set()
        result: list[ChangeOfCharacter] = []
        for event in events:
            key = event.broken_swing.id
            if key in seen:
                continue
            seen.add(key)
            result.append(event)
        return result
