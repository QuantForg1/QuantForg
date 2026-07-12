"""Unit tests for FairValueGapEngine orchestration and events."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.events.fair_value_gap import (
    FairValueGapDetected,
    FairValueGapStateChanged,
    GapPartiallyFilled,
)
from app.domain.fair_value_gap.engine import FairValueGapEngine
from app.domain.fair_value_gap.enums import FairValueGapState
from app.domain.market_data.timeframe import Timeframe
from tests.unit.fair_value_gap_fakes import (
    InMemoryFairValueGapRepository,
    InMemoryPriceHistory,
    NullMarketStructure,
    NullOrderBlockSnapshot,
    bullish_fvg_series,
)


@pytest.mark.unit
class TestFairValueGapEngine:
    @pytest.mark.asyncio
    async def test_analyze_emits_events_and_snapshot(self) -> None:
        candles = bullish_fvg_series()
        repo = InMemoryFairValueGapRepository()
        engine = FairValueGapEngine(
            prices=InMemoryPriceHistory(candles),
            structure=NullMarketStructure(),
            order_blocks=NullOrderBlockSnapshot(),
            repository=repo,
        )
        result = await engine.analyze(
            "EURUSD",
            Timeframe.M15,
            persist=True,
            as_of=datetime(2026, 1, 2, tzinfo=UTC),
        )

        assert result.snapshot.symbol_code.value == "EURUSD"
        assert len(result.snapshot.gaps) >= 1
        gap = result.snapshot.gaps[0]
        assert gap.state in {
            FairValueGapState.ACTIVE,
            FairValueGapState.PARTIALLY_FILLED,
            FairValueGapState.FILLED,
        }
        assert gap.quality is not None
        assert len(repo.items) == 1

        types = {type(e) for e in result.events}
        assert FairValueGapDetected in types
        assert FairValueGapStateChanged in types
        assert GapPartiallyFilled in types

    @pytest.mark.asyncio
    async def test_second_pass_suppresses_duplicate_detections(self) -> None:
        candles = bullish_fvg_series()
        repo = InMemoryFairValueGapRepository()
        engine = FairValueGapEngine(
            prices=InMemoryPriceHistory(candles),
            repository=repo,
        )
        first = await engine.analyze("EURUSD", "M15", persist=True)
        second = await engine.analyze("EURUSD", "M15", persist=True)

        assert any(isinstance(e, FairValueGapDetected) for e in first.events)
        assert not any(isinstance(e, FairValueGapDetected) for e in second.events)
