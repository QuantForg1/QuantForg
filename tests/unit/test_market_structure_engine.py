"""Unit tests for MarketStructureEngine orchestration and events."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.events.market_structure import (
    BreakOfStructureDetected,
    StructureChanged,
    SwingDetected,
    TrendChanged,
)
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.engine import MarketStructureEngine
from app.domain.market_structure.enums import TrendDirection
from app.domain.market_structure.structure_analyzer import StructureAnalyzer
from app.domain.market_structure.swing_detector import SwingDetector
from app.domain.market_structure.trend_classifier import TrendClassifier
from tests.unit.market_structure_fakes import (
    InMemoryPriceSeries,
    InMemoryStructureRepository,
    make_candle,
    uptrend_series,
)


@pytest.mark.unit
class TestMarketStructureEngine:
    @pytest.mark.asyncio
    async def test_analyze_emits_events_and_snapshot(self) -> None:
        candles = uptrend_series()
        repo = InMemoryStructureRepository()
        engine = MarketStructureEngine(
            prices=InMemoryPriceSeries(candles),
            swings=SwingDetector(),
            trends=TrendClassifier(),
            analyzer=StructureAnalyzer(),
            repository=repo,
            swing_left=1,
            swing_right=1,
        )

        result = await engine.analyze(
            "EURUSD",
            Timeframe.M15,
            persist=True,
            as_of=datetime(2026, 1, 2, tzinfo=UTC),
        )

        assert result.snapshot.symbol_code.value == "EURUSD"
        assert result.snapshot.timeframe is Timeframe.M15
        assert result.snapshot.trend.direction == TrendDirection.UP
        assert len(result.snapshot.swings) >= 4
        assert len(repo.items) == 1

        types = {type(e) for e in result.events}
        assert SwingDetected in types
        assert StructureChanged in types
        assert TrendChanged in types
        assert BreakOfStructureDetected in types

    @pytest.mark.asyncio
    async def test_second_pass_suppresses_duplicate_swings_and_trend(self) -> None:
        candles = uptrend_series()
        repo = InMemoryStructureRepository()
        engine = MarketStructureEngine(
            prices=InMemoryPriceSeries(candles),
            swings=SwingDetector(),
            trends=TrendClassifier(),
            repository=repo,
            swing_left=1,
            swing_right=1,
        )
        first = await engine.analyze("EURUSD", "M15", persist=True)
        second = await engine.analyze("EURUSD", "M15", persist=True)

        assert any(isinstance(e, SwingDetected) for e in first.events)
        assert not any(isinstance(e, SwingDetected) for e in second.events)
        assert any(isinstance(e, StructureChanged) for e in second.events)
        assert not any(isinstance(e, TrendChanged) for e in second.events)

    @pytest.mark.asyncio
    async def test_multi_symbol_isolation(self) -> None:
        eurusd = uptrend_series()
        gbp = [
            make_candle(index=i, high=h, low=low, close=c, symbol="GBPUSD")
            for i, (h, low, c) in enumerate(
                [
                    ("2.0", "1.5", "1.8"),
                    ("2.2", "1.6", "2.1"),
                    ("2.1", "1.55", "1.9"),
                    ("1.9", "1.4", "1.5"),
                    ("2.0", "1.5", "1.8"),
                    ("2.3", "1.7", "2.2"),
                    ("2.2", "1.8", "2.0"),
                    ("2.1", "1.6", "1.7"),
                    ("2.4", "1.9", "2.35"),
                ]
            )
        ]
        engine = MarketStructureEngine(
            prices=InMemoryPriceSeries(eurusd + gbp),
            swings=SwingDetector(),
            trends=TrendClassifier(),
            swing_left=1,
            swing_right=1,
        )
        eu = await engine.analyze("EURUSD", Timeframe.M15)
        gp = await engine.analyze("GBPUSD", Timeframe.M15)
        assert eu.snapshot.symbol_code.value == "EURUSD"
        assert gp.snapshot.symbol_code.value == "GBPUSD"
        assert eu.snapshot.id != gp.snapshot.id
