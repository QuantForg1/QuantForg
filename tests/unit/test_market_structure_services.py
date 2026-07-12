"""Unit tests for SwingDetector, StructureAnalyzer, and TrendClassifier."""

from __future__ import annotations

import pytest

from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import (
    StructureRole,
    SwingKind,
    TrendDirection,
)
from app.domain.market_structure.structure_analyzer import StructureAnalyzer
from app.domain.market_structure.swing_detector import SwingDetector
from app.domain.market_structure.trend_classifier import TrendClassifier
from app.domain.value_objects.identity import SymbolCode
from tests.unit.market_structure_fakes import make_candle, uptrend_series


@pytest.mark.unit
class TestSwingDetector:
    def test_detects_fractal_swings(self) -> None:
        candles = uptrend_series()
        swings = SwingDetector().detect(candles, left=1, right=1)
        kinds = [(s.bar_index, s.kind, str(s.price)) for s in swings]
        assert (1, SwingKind.HIGH, "12") in kinds
        assert (3, SwingKind.LOW, "7") in kinds
        assert (5, SwingKind.HIGH, "13") in kinds
        assert (7, SwingKind.LOW, "8.5") in kinds

    def test_requires_enough_bars(self) -> None:
        candles = [make_candle(index=0, high="1", low="0.5")]
        assert SwingDetector().detect(candles, left=2, right=2) == ()

    def test_swing_ids_are_stable_across_runs(self) -> None:
        candles = uptrend_series()
        detector = SwingDetector()
        first = detector.detect(candles, left=1, right=1)
        second = detector.detect(candles, left=1, right=1)
        assert [s.id for s in first] == [s.id for s in second]


@pytest.mark.unit
class TestStructureAnalyzerAndTrend:
    def test_hh_hl_roles_and_uptrend(self) -> None:
        candles = uptrend_series()
        swings = SwingDetector().detect(candles, left=1, right=1)
        analyzer = StructureAnalyzer()
        nodes = analyzer.build_nodes(swings)
        roles = [n.role for n in nodes]
        # first high/low unknown, then HH and HL
        assert StructureRole.HIGHER_HIGH in roles
        assert StructureRole.HIGHER_LOW in roles

        trend = TrendClassifier(lookback=6).classify(
            nodes,
            symbol_code=SymbolCode.of("EURUSD"),
            timeframe=Timeframe.M15,
        )
        assert trend.direction == TrendDirection.UP

    def test_bos_in_uptrend(self) -> None:
        candles = uptrend_series()
        swings = SwingDetector().detect(candles, left=1, right=1)
        analyzer = StructureAnalyzer()
        nodes = analyzer.build_nodes(swings)
        trend = TrendClassifier().classify(
            nodes,
            symbol_code=SymbolCode.of("EURUSD"),
            timeframe=Timeframe.M15,
        )
        result = analyzer.detect_breaks(
            swings=swings,
            candles=candles,
            trend=trend.direction,
        )
        assert len(result.breaks_of_structure) >= 1
        bos = result.breaks_of_structure[0]
        assert bos.trend_direction == TrendDirection.UP
        assert bos.broken_swing.kind == SwingKind.HIGH

    def test_choch_against_uptrend(self) -> None:
        # Extend the uptrend series with a close below the last swing low (8.5).
        candles = [
            *uptrend_series(),
            make_candle(index=9, high="9", low="7", close="7.2", open_="8.5"),
        ]
        swings = SwingDetector().detect(candles, left=1, right=1)
        analyzer = StructureAnalyzer()
        result = analyzer.detect_breaks(
            swings=swings,
            candles=candles,
            trend=TrendDirection.UP,
        )
        assert len(result.changes_of_character) >= 1
        choch = result.changes_of_character[0]
        assert choch.previous_trend == TrendDirection.UP
        assert choch.broken_swing.kind == SwingKind.LOW

    def test_no_breaks_in_range(self) -> None:
        candles = uptrend_series()
        swings = SwingDetector().detect(candles, left=1, right=1)
        result = StructureAnalyzer().detect_breaks(
            swings=swings,
            candles=candles,
            trend=TrendDirection.RANGE,
        )
        assert result.breaks_of_structure == ()
        assert result.changes_of_character == ()
