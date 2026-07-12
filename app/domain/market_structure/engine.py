"""MarketStructureEngine — orchestrate swing → structure → trend → snapshot.

Why it exists
-------------
Single entry point that loads a price series, detects swings, analyses
structure, classifies trend, optionally compares to a prior snapshot, and
returns an immutable :class:`StructureSnapshot` plus domain events.
Does not trade, call MetaTrader, run AI, or emit entry signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.events.base import DomainEvent
from app.domain.events.market_structure import (
    BreakOfStructureDetected,
    ChangeOfCharacterDetected,
    StructureChanged,
    SwingDetected,
    TrendChanged,
)
from app.domain.interfaces.market_structure import (
    PriceSeriesPort,
    StructureRepositoryPort,
    SwingDetectorPort,
    TrendAnalyzerPort,
)
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.models import StructureSnapshot
from app.domain.market_structure.structure_analyzer import StructureAnalyzer
from app.domain.value_objects.identity import SymbolCode


@dataclass(frozen=True, slots=True)
class MarketStructureResult:
    """Engine output: immutable snapshot plus pending domain events."""

    snapshot: StructureSnapshot
    events: tuple[DomainEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketStructureEngine:
    """Orchestrate market-structure analysis for one symbol/timeframe."""

    prices: PriceSeriesPort
    swings: SwingDetectorPort
    trends: TrendAnalyzerPort
    analyzer: StructureAnalyzer = field(default_factory=StructureAnalyzer)
    repository: StructureRepositoryPort | None = None
    swing_left: int = 2
    swing_right: int = 2
    candle_limit: int = 500

    async def analyze(
        self,
        symbol_code: str | SymbolCode,
        timeframe: Timeframe | str,
        *,
        persist: bool = False,
        as_of: datetime | None = None,
    ) -> MarketStructureResult:
        """Run a full structure analysis pass and return snapshot + events."""
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

        candles = await self.prices.get_candles(
            code,
            tf,
            limit=self.candle_limit,
        )
        swing_points = self.swings.detect(
            candles,
            left=self.swing_left,
            right=self.swing_right,
        )
        nodes = self.analyzer.build_nodes(swing_points)
        trend = self.trends.classify(nodes, symbol_code=code, timeframe=tf)
        # Ensure trend as_of aligns with analysis moment when classifier used now.
        analysis = self.analyzer.detect_breaks(
            swings=swing_points,
            candles=candles,
            trend=trend.direction,
        )

        snapshot = StructureSnapshot(
            symbol_code=code,
            timeframe=tf,
            as_of=moment,
            swings=swing_points,
            nodes=analysis.nodes,
            trend=trend,
            breaks_of_structure=analysis.breaks_of_structure,
            changes_of_character=analysis.changes_of_character,
        )

        previous: StructureSnapshot | None = None
        if self.repository is not None:
            previous = await self.repository.get_latest_snapshot(code, tf)

        events = self._build_events(snapshot, previous)

        if persist and self.repository is not None:
            await self.repository.save_snapshot(snapshot)

        return MarketStructureResult(snapshot=snapshot, events=tuple(events))

    def _build_events(
        self,
        snapshot: StructureSnapshot,
        previous: StructureSnapshot | None,
    ) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        previous_swing_ids = (
            {s.id for s in previous.swings} if previous is not None else set()
        )
        for swing in snapshot.swings:
            if swing.id in previous_swing_ids:
                continue
            events.append(
                SwingDetected(
                    symbol_code=str(swing.symbol_code),
                    timeframe=swing.timeframe.value,
                    swing_id=swing.id,
                    kind=swing.kind.value,
                    price=str(swing.price),
                    occurred_at=swing.timestamp,
                )
            )

        events.append(
            StructureChanged(
                snapshot_id=snapshot.id,
                symbol_code=str(snapshot.symbol_code),
                timeframe=snapshot.timeframe.value,
                trend_direction=snapshot.trend.direction.value,
                node_count=len(snapshot.nodes),
                occurred_at=snapshot.as_of,
            )
        )

        previous_bos = (
            {b.broken_swing.id for b in previous.breaks_of_structure}
            if previous is not None
            else set()
        )
        for bos in snapshot.breaks_of_structure:
            if bos.broken_swing.id in previous_bos:
                continue
            events.append(
                BreakOfStructureDetected(
                    bos_id=bos.id,
                    symbol_code=str(bos.symbol_code),
                    timeframe=bos.timeframe.value,
                    trend_direction=bos.trend_direction.value,
                    break_price=str(bos.break_price),
                    occurred_at=bos.broken_at,
                )
            )

        previous_choch = (
            {c.broken_swing.id for c in previous.changes_of_character}
            if previous is not None
            else set()
        )
        for choch in snapshot.changes_of_character:
            if choch.broken_swing.id in previous_choch:
                continue
            events.append(
                ChangeOfCharacterDetected(
                    choch_id=choch.id,
                    symbol_code=str(choch.symbol_code),
                    timeframe=choch.timeframe.value,
                    previous_trend=choch.previous_trend.value,
                    break_price=str(choch.break_price),
                    occurred_at=choch.broken_at,
                )
            )

        if previous is None or previous.trend.direction != snapshot.trend.direction:
            prev_dir = (
                previous.trend.direction.value if previous is not None else "unknown"
            )
            events.append(
                TrendChanged(
                    symbol_code=str(snapshot.symbol_code),
                    timeframe=snapshot.timeframe.value,
                    previous_direction=prev_dir,
                    current_direction=snapshot.trend.direction.value,
                    trend_id=snapshot.trend.id,
                    occurred_at=snapshot.as_of,
                )
            )

        return events
