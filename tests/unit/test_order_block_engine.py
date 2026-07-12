"""Unit tests for OrderBlockEngine orchestration and events."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.events.order_block import (
    MitigationDetected,
    OrderBlockDetected,
    OrderBlockStateChanged,
    OrderBlockValidated,
)
from app.domain.market_data.timeframe import Timeframe
from app.domain.order_block.engine import OrderBlockEngine
from app.domain.order_block.enums import OrderBlockState
from tests.unit.order_block_fakes import (
    EmptyLiquiditySnapshot,
    InMemoryMarketStructure,
    InMemoryOrderBlockRepository,
    InMemoryPriceHistory,
    bullish_ob_series,
    structure_with_bullish_bos,
)


@pytest.mark.unit
class TestOrderBlockEngine:
    @pytest.mark.asyncio
    async def test_analyze_emits_events_and_snapshot(self) -> None:
        candles = bullish_ob_series()
        structure = structure_with_bullish_bos(candles)
        repo = InMemoryOrderBlockRepository()
        engine = OrderBlockEngine(
            prices=InMemoryPriceHistory(candles),
            structure=InMemoryMarketStructure(structure),
            liquidity=EmptyLiquiditySnapshot(),
            repository=repo,
        )
        result = await engine.analyze(
            "EURUSD",
            Timeframe.M15,
            persist=True,
            as_of=datetime(2026, 1, 2, tzinfo=UTC),
        )

        assert result.snapshot.symbol_code.value == "EURUSD"
        assert len(result.snapshot.order_blocks) >= 1
        block = result.snapshot.order_blocks[0]
        assert block.state in {
            OrderBlockState.ACTIVE,
            OrderBlockState.MITIGATED,
            OrderBlockState.BREAKER,
        }
        assert block.quality is not None
        assert len(repo.items) == 1

        types = {type(e) for e in result.events}
        assert OrderBlockDetected in types
        assert OrderBlockValidated in types
        assert OrderBlockStateChanged in types
        assert MitigationDetected in types

    @pytest.mark.asyncio
    async def test_second_pass_suppresses_duplicate_detections(self) -> None:
        candles = bullish_ob_series()
        structure = structure_with_bullish_bos(candles)
        repo = InMemoryOrderBlockRepository()
        engine = OrderBlockEngine(
            prices=InMemoryPriceHistory(candles),
            structure=InMemoryMarketStructure(structure),
            repository=repo,
        )
        first = await engine.analyze("EURUSD", "M15", persist=True)
        second = await engine.analyze("EURUSD", "M15", persist=True)

        assert any(isinstance(e, OrderBlockDetected) for e in first.events)
        assert not any(isinstance(e, OrderBlockDetected) for e in second.events)
