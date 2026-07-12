"""Unit tests for FVG detector, fill, invalidation, quality, lifecycle."""

from __future__ import annotations

import pytest

from app.domain.exceptions.base import ValidationError
from app.domain.fair_value_gap.detector import FairValueGapDetector
from app.domain.fair_value_gap.enums import (
    FairValueGapSide,
    FairValueGapState,
    FillKind,
    QualityGrade,
)
from app.domain.fair_value_gap.fill_detector import GapFillDetector
from app.domain.fair_value_gap.invalidation_detector import GapInvalidationDetector
from app.domain.fair_value_gap.models import GAP_TRANSITIONS
from app.domain.fair_value_gap.quality_evaluator import GapQualityEvaluator
from tests.unit.fair_value_gap_fakes import (
    bullish_fvg_full_fill_series,
    bullish_fvg_invalidate_series,
    bullish_fvg_series,
)


@pytest.mark.unit
class TestGapLifecycle:
    def test_allowed_transitions(self) -> None:
        assert FairValueGapState.ACTIVE in GAP_TRANSITIONS[FairValueGapState.DETECTED]
        assert (
            FairValueGapState.PARTIALLY_FILLED
            in GAP_TRANSITIONS[FairValueGapState.ACTIVE]
        )
        assert GAP_TRANSITIONS[FairValueGapState.EXPIRED] == frozenset()

    def test_illegal_transition_raises(self) -> None:
        gaps = FairValueGapDetector().detect(bullish_fvg_series()[:3])
        gap = gaps[0]
        with pytest.raises(ValidationError):
            gap.transition(FairValueGapState.DETECTED, at=gap.lifecycle.detected_at)


@pytest.mark.unit
class TestFairValueGapServices:
    def test_detects_bullish_fvg(self) -> None:
        candles = bullish_fvg_series()[:3]
        gaps = FairValueGapDetector().detect(candles)
        assert len(gaps) >= 1
        gap = gaps[0]
        assert gap.side == FairValueGapSide.BULLISH
        assert gap.state == FairValueGapState.ACTIVE
        assert str(gap.zone.low_price) == "10"
        assert str(gap.zone.high_price) == "11.2"
        again = FairValueGapDetector().detect(candles)
        assert again[0].id == gap.id

    def test_partial_fill(self) -> None:
        candles = bullish_fvg_series()
        gaps = FairValueGapDetector().detect(candles[:3])
        result = GapFillDetector().detect(gaps, candles)
        assert len(result.fills) >= 1
        assert result.fills[0].kind == FillKind.PARTIAL
        assert result.gaps[0].state == FairValueGapState.PARTIALLY_FILLED
        assert result.gaps[0].lifecycle.fill_ratio > 0

    def test_full_fill(self) -> None:
        candles = bullish_fvg_full_fill_series()
        gaps = FairValueGapDetector().detect(candles[:3])
        result = GapFillDetector().detect(gaps, candles)
        assert any(f.kind == FillKind.FULL for f in result.fills)
        assert result.gaps[0].state == FairValueGapState.FILLED

    def test_invalidation(self) -> None:
        candles = bullish_fvg_invalidate_series()
        gaps = FairValueGapDetector().detect(candles[:3])
        result = GapInvalidationDetector().detect(gaps, candles)
        assert len(result.invalidations) >= 1
        assert result.gaps[0].state == FairValueGapState.INVALIDATED

    def test_quality_assigned(self) -> None:
        candles = bullish_fvg_series()[:3]
        gaps = FairValueGapDetector().detect(candles)
        scored = GapQualityEvaluator().evaluate(gaps, candles)
        assert scored[0].quality is not None
        assert scored[0].quality.grade in set(QualityGrade)
