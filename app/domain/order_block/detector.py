"""OrderBlockDetector — find OBs from structure displacement + candles.

Why it exists
-------------
Locates the last opposing candle before a BOS/CHoCH displacement and records
it as an order block. Structural observation only — not a trade signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.market_data.candle import Candle
from app.domain.market_structure.enums import TrendDirection
from app.domain.market_structure.models import (
    BreakOfStructure,
    ChangeOfCharacter,
    StructureSnapshot,
)
from app.domain.order_block.enums import (
    OrderBlockOrigin,
    OrderBlockSide,
    OrderBlockState,
)
from app.domain.order_block.ids import order_block_id, zone_id
from app.domain.order_block.models import OrderBlock, OrderBlockZone


@dataclass(frozen=True, slots=True)
class OrderBlockDetector:
    """Detect candidate order blocks from structure + OHLC series."""

    lookback: int = 12

    def detect(
        self,
        candles: Sequence[Candle],
        structure: StructureSnapshot | None,
    ) -> tuple[OrderBlock, ...]:
        """Return newly detected order blocks (state=DETECTED)."""
        if not candles or structure is None:
            return ()

        blocks: list[OrderBlock] = []
        seen: set[UUID] = set()

        for bos in structure.breaks_of_structure:
            block = self._from_bos(candles, bos)
            if block is not None and block.id not in seen:
                seen.add(block.id)
                blocks.append(block)

        for choch in structure.changes_of_character:
            block = self._from_choch(candles, choch)
            if block is not None and block.id not in seen:
                seen.add(block.id)
                blocks.append(block)

        return tuple(blocks)

    def _from_bos(
        self,
        candles: Sequence[Candle],
        bos: BreakOfStructure,
    ) -> OrderBlock | None:
        break_index = self._index_at_or_after(candles, bos.broken_at)
        if break_index is None:
            return None
        if bos.trend_direction == TrendDirection.UP:
            return self._bullish_ob(
                candles,
                break_index,
                origin=OrderBlockOrigin.BOS,
                source_id=bos.id,
            )
        if bos.trend_direction == TrendDirection.DOWN:
            return self._bearish_ob(
                candles,
                break_index,
                origin=OrderBlockOrigin.BOS,
                source_id=bos.id,
            )
        return None

    def _from_choch(
        self,
        candles: Sequence[Candle],
        choch: ChangeOfCharacter,
    ) -> OrderBlock | None:
        break_index = self._index_at_or_after(candles, choch.broken_at)
        if break_index is None:
            return None
        # Against prior trend: UP CHoCH breaks a low → bearish displacement context
        # yields a bearish OB (last up-close). DOWN CHoCH → bullish OB.
        if choch.previous_trend == TrendDirection.UP:
            return self._bearish_ob(
                candles,
                break_index,
                origin=OrderBlockOrigin.CHOCH,
                source_id=choch.id,
            )
        if choch.previous_trend == TrendDirection.DOWN:
            return self._bullish_ob(
                candles,
                break_index,
                origin=OrderBlockOrigin.CHOCH,
                source_id=choch.id,
            )
        return None

    def _bullish_ob(
        self,
        candles: Sequence[Candle],
        break_index: int,
        *,
        origin: OrderBlockOrigin,
        source_id: UUID,
    ) -> OrderBlock | None:
        # Last down-close candle before displacement.
        start = max(0, break_index - self.lookback)
        origin_idx = None
        for i in range(break_index - 1, start - 1, -1):
            c = candles[i]
            if c.close.value < c.open.value:
                origin_idx = i
                break
        if origin_idx is None:
            return None
        return self._build(
            candles,
            origin_idx,
            break_index,
            side=OrderBlockSide.BULLISH,
            origin=origin,
            source_id=source_id,
        )

    def _bearish_ob(
        self,
        candles: Sequence[Candle],
        break_index: int,
        *,
        origin: OrderBlockOrigin,
        source_id: UUID,
    ) -> OrderBlock | None:
        start = max(0, break_index - self.lookback)
        origin_idx = None
        for i in range(break_index - 1, start - 1, -1):
            c = candles[i]
            if c.close.value > c.open.value:
                origin_idx = i
                break
        if origin_idx is None:
            return None
        return self._build(
            candles,
            origin_idx,
            break_index,
            side=OrderBlockSide.BEARISH,
            origin=origin,
            source_id=source_id,
        )

    def _build(
        self,
        candles: Sequence[Candle],
        origin_idx: int,
        displacement_idx: int,
        *,
        side: OrderBlockSide,
        origin: OrderBlockOrigin,
        source_id: UUID,
    ) -> OrderBlock:
        candle = candles[origin_idx]
        symbol = candle.symbol_code
        tf = candle.timeframe
        zone = OrderBlockZone(
            symbol_code=symbol,
            timeframe=tf,
            low_price=candle.low,
            high_price=candle.high,
            bar_index=origin_idx,
            formed_at=candle.close_time,
            id=zone_id(
                str(symbol),
                tf.value,
                str(candle.low),
                str(candle.high),
                origin_idx,
            ),
        )
        return OrderBlock(
            symbol_code=symbol,
            timeframe=tf,
            side=side,
            zone=zone,
            origin=origin,
            state=OrderBlockState.DETECTED,
            formed_at=candle.close_time,
            origin_bar_index=origin_idx,
            displacement_bar_index=displacement_idx,
            source_event_id=source_id,
            id=order_block_id(
                str(symbol),
                tf.value,
                side.value,
                origin_idx,
                str(candle.low),
                str(candle.high),
            ),
        )

    @staticmethod
    def _index_at_or_after(
        candles: Sequence[Candle],
        when: datetime,
    ) -> int | None:
        for i, candle in enumerate(candles):
            if candle.close_time >= when:
                return i
        return len(candles) - 1 if candles else None
