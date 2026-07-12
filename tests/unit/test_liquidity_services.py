"""Unit tests for equal detectors, zone builder, and sweep detector."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.liquidity.enums import (
    LiquidityPoolStatus,
    LiquiditySide,
    SweepKind,
)
from app.domain.liquidity.equal_high_detector import EqualHighDetector
from app.domain.liquidity.equal_low_detector import EqualLowDetector
from app.domain.liquidity.sweep_detector import LiquiditySweepDetector
from app.domain.liquidity.zone_builder import LiquidityZoneBuilder
from app.domain.market_structure.swing_detector import SwingDetector
from tests.unit.liquidity_fakes import (
    equal_highs_sweep_series,
    equal_lows_sweep_series,
)


@pytest.mark.unit
class TestEqualDetectors:
    def test_detects_equal_highs(self) -> None:
        candles = equal_highs_sweep_series()
        swings = SwingDetector().detect(candles, left=1, right=1)
        clusters = EqualHighDetector(tolerance=Decimal("0")).detect(swings)
        assert len(clusters) >= 1
        eqh = clusters[0]
        assert eqh.touch_count >= 2
        assert str(eqh.price) == "10"
        # Stable identity across runs
        again = EqualHighDetector().detect(swings)
        assert again[0].id == eqh.id

    def test_detects_equal_lows(self) -> None:
        candles = equal_lows_sweep_series()
        swings = SwingDetector().detect(candles, left=1, right=1)
        clusters = EqualLowDetector(tolerance=Decimal("0")).detect(swings)
        assert len(clusters) >= 1
        assert str(clusters[0].price) == "7"
        assert clusters[0].touch_count >= 2


@pytest.mark.unit
class TestZoneBuilderAndSweeps:
    def test_builds_sell_side_pool_and_zone(self) -> None:
        candles = equal_highs_sweep_series()
        swings = SwingDetector().detect(candles, left=1, right=1)
        eqh = EqualHighDetector().detect(swings)
        built = LiquidityZoneBuilder().build(eqh, ())
        assert len(built.pools) == len(eqh)
        assert built.pools[0].side == LiquiditySide.SELL_SIDE
        assert built.pools[0].status == LiquidityPoolStatus.ACTIVE
        assert built.zones[0].side == LiquiditySide.SELL_SIDE
        assert built.zones[0].id == LiquidityZoneBuilder().build(eqh, ()).zones[0].id

    def test_high_sweep_of_equal_highs(self) -> None:
        candles = equal_highs_sweep_series()
        swings = SwingDetector().detect(candles, left=1, right=1)
        eqh = EqualHighDetector().detect(swings)
        built = LiquidityZoneBuilder().build(eqh, ())
        result = LiquiditySweepDetector().detect(built.pools, candles)
        assert len(result.sweeps) >= 1
        sweep = result.sweeps[0]
        assert sweep.kind == SweepKind.HIGH_SWEEP
        assert result.pools[0].status == LiquidityPoolStatus.SWEPT

    def test_low_sweep_of_equal_lows(self) -> None:
        candles = equal_lows_sweep_series()
        swings = SwingDetector().detect(candles, left=1, right=1)
        eql = EqualLowDetector().detect(swings)
        built = LiquidityZoneBuilder().build((), eql)
        result = LiquiditySweepDetector().detect(built.pools, candles)
        assert len(result.sweeps) >= 1
        assert result.sweeps[0].kind == SweepKind.LOW_SWEEP
        assert result.pools[0].status == LiquidityPoolStatus.SWEPT
