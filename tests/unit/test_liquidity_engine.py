"""Unit tests for LiquidityEngine orchestration and events."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.events.liquidity import (
    LiquidityPoolDetected,
    LiquidityStateChanged,
    LiquiditySweepDetected,
    LiquidityZoneCreated,
)
from app.domain.liquidity.engine import LiquidityEngine
from app.domain.liquidity.enums import LiquidityStateKind, SweepKind
from app.domain.liquidity.equal_high_detector import EqualHighDetector
from app.domain.liquidity.equal_low_detector import EqualLowDetector
from app.domain.market_data.timeframe import Timeframe
from tests.unit.liquidity_fakes import (
    InMemoryLiquidityRepository,
    InMemoryPriceHistory,
    InMemorySwingProvider,
    NullMarketStructure,
    equal_highs_sweep_series,
    make_candle,
)


def _engine(candles, repo=None) -> LiquidityEngine:
    return LiquidityEngine(
        prices=InMemoryPriceHistory(candles),
        swings=InMemorySwingProvider(candles),
        structure=NullMarketStructure(),
        repository=repo,
        equal_highs=EqualHighDetector(),
        equal_lows=EqualLowDetector(),
        swing_left=1,
        swing_right=1,
    )


@pytest.mark.unit
class TestLiquidityEngine:
    @pytest.mark.asyncio
    async def test_analyze_emits_events_and_snapshot(self) -> None:
        candles = equal_highs_sweep_series()
        repo = InMemoryLiquidityRepository()
        result = await _engine(candles, repo).analyze(
            "EURUSD",
            Timeframe.M15,
            persist=True,
            as_of=datetime(2026, 1, 2, tzinfo=UTC),
        )

        assert result.snapshot.symbol_code.value == "EURUSD"
        assert result.snapshot.timeframe is Timeframe.M15
        assert len(result.snapshot.equal_highs) >= 1
        assert len(result.snapshot.pools) >= 1
        assert len(result.snapshot.zones) >= 1
        assert len(result.snapshot.sweeps) >= 1
        assert result.snapshot.sweeps[0].kind == SweepKind.HIGH_SWEEP
        assert result.snapshot.state.kind in {
            LiquidityStateKind.SELL_SIDE_SWEPT,
            LiquidityStateKind.SELL_SIDE_HEAVY,
            LiquidityStateKind.BALANCED,
            LiquidityStateKind.BUY_SIDE_HEAVY,
        }
        assert len(repo.items) == 1

        types = {type(e) for e in result.events}
        assert LiquidityPoolDetected in types
        assert LiquidityZoneCreated in types
        assert LiquiditySweepDetected in types
        assert LiquidityStateChanged in types

    @pytest.mark.asyncio
    async def test_second_pass_suppresses_duplicate_pool_events(self) -> None:
        candles = equal_highs_sweep_series()
        repo = InMemoryLiquidityRepository()
        engine = _engine(candles, repo)
        first = await engine.analyze("EURUSD", "M15", persist=True)
        second = await engine.analyze("EURUSD", "M15", persist=True)

        assert any(isinstance(e, LiquidityPoolDetected) for e in first.events)
        assert not any(isinstance(e, LiquidityPoolDetected) for e in second.events)
        assert not any(isinstance(e, LiquidityZoneCreated) for e in second.events)
        assert not any(isinstance(e, LiquiditySweepDetected) for e in second.events)
        assert not any(isinstance(e, LiquidityStateChanged) for e in second.events)

    @pytest.mark.asyncio
    async def test_multi_symbol_isolation(self) -> None:
        eurusd = equal_highs_sweep_series()
        gbp = [
            make_candle(index=i, high=h, low=low, close=c, symbol="GBPUSD")
            for i, (h, low, c) in enumerate(
                [
                    ("2.0", "1.5", "1.8"),
                    ("2.2", "1.6", "2.1"),
                    ("2.1", "1.55", "1.9"),
                    ("1.9", "1.4", "1.5"),
                    ("2.0", "1.5", "1.8"),
                    ("2.2", "1.7", "2.0"),
                    ("2.1", "1.8", "1.95"),
                    ("2.0", "1.6", "1.7"),
                    ("2.3", "1.9", "2.1"),
                ]
            )
        ]
        engine = _engine(eurusd + gbp)
        eu = await engine.analyze("EURUSD", Timeframe.M15)
        gp = await engine.analyze("GBPUSD", Timeframe.M15)
        assert eu.snapshot.symbol_code.value == "EURUSD"
        assert gp.snapshot.symbol_code.value == "GBPUSD"
        assert eu.snapshot.id != gp.snapshot.id
