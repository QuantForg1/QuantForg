"""Unit tests for order-block detectors, validator, lifecycle, and quality."""

from __future__ import annotations

import pytest

from app.domain.exceptions.base import ValidationError
from app.domain.order_block.breaker_detector import BreakerDetector
from app.domain.order_block.detector import OrderBlockDetector
from app.domain.order_block.enums import (
    OrderBlockSide,
    OrderBlockState,
    QualityGrade,
)
from app.domain.order_block.mitigation_detector import MitigationDetector
from app.domain.order_block.models import ORDER_BLOCK_TRANSITIONS
from app.domain.order_block.strength_evaluator import OrderBlockStrengthEvaluator
from app.domain.order_block.validator import OrderBlockValidator
from tests.unit.order_block_fakes import (
    bullish_ob_series,
    bullish_ob_then_breaker_series,
    structure_with_bullish_bos,
)


@pytest.mark.unit
class TestOrderBlockLifecycle:
    def test_allowed_transitions(self) -> None:
        assert (
            OrderBlockState.ACTIVE in ORDER_BLOCK_TRANSITIONS[OrderBlockState.VALIDATED]
        )
        assert (
            OrderBlockState.BREAKER in ORDER_BLOCK_TRANSITIONS[OrderBlockState.ACTIVE]
        )
        assert ORDER_BLOCK_TRANSITIONS[OrderBlockState.EXPIRED] == frozenset()

    def test_illegal_transition_raises(self) -> None:
        candles = bullish_ob_series()
        structure = structure_with_bullish_bos(candles)
        block = OrderBlockDetector().detect(candles, structure)[0]
        with pytest.raises(ValidationError):
            block.transition(OrderBlockState.BREAKER)


@pytest.mark.unit
class TestOrderBlockServices:
    def test_detects_bullish_order_block(self) -> None:
        candles = bullish_ob_series()
        structure = structure_with_bullish_bos(candles)
        blocks = OrderBlockDetector().detect(candles, structure)
        assert len(blocks) >= 1
        ob = blocks[0]
        assert ob.side == OrderBlockSide.BULLISH
        assert ob.state == OrderBlockState.DETECTED
        assert ob.origin_bar_index == 3
        # Stable id
        again = OrderBlockDetector().detect(candles, structure)
        assert again[0].id == ob.id

    def test_validator_activates_strong_blocks(self) -> None:
        candles = bullish_ob_series()
        structure = structure_with_bullish_bos(candles)
        detected = OrderBlockDetector().detect(candles, structure)
        result = OrderBlockValidator().validate(detected, candles)
        assert len(result.activated) >= 1
        assert result.activated[0].state == OrderBlockState.ACTIVE
        assert result.expired == ()

    def test_mitigation_of_active_block(self) -> None:
        candles = bullish_ob_series()
        structure = structure_with_bullish_bos(candles)
        detected = OrderBlockDetector().detect(candles, structure)
        active = OrderBlockValidator().validate(detected, candles).activated
        mit = MitigationDetector().detect(active, candles)
        assert len(mit.mitigations) >= 1
        assert mit.blocks[0].state == OrderBlockState.MITIGATED

    def test_breaker_after_close_through(self) -> None:
        # Validate on pre-break series, then append invalidating bar.
        candles = bullish_ob_series()[:7]
        structure = structure_with_bullish_bos(candles)
        detected = OrderBlockDetector().detect(candles, structure)
        active = OrderBlockValidator().validate(detected, candles).activated
        assert active and active[0].state == OrderBlockState.ACTIVE

        broken_series = bullish_ob_then_breaker_series()
        brk = BreakerDetector().detect(active, broken_series)
        assert len(brk.breakers) >= 1
        assert brk.blocks[0].state == OrderBlockState.BREAKER

    def test_strength_assigns_quality(self) -> None:
        candles = bullish_ob_series()
        structure = structure_with_bullish_bos(candles)
        detected = OrderBlockDetector().detect(candles, structure)
        active = OrderBlockValidator().validate(detected, candles).activated
        scored = OrderBlockStrengthEvaluator().evaluate(active, candles)
        assert scored[0].quality is not None
        assert scored[0].quality.grade in set(QualityGrade)
        assert scored[0].quality.score >= 0
