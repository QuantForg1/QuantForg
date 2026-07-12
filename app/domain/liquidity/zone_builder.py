"""LiquidityZoneBuilder — turn equal highs/lows into pools and zones.

Why it exists
-------------
Normalises equal-level detections into :class:`LiquidityPool` /
:class:`LiquidityZone` records with deterministic identities.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.liquidity.enums import LiquidityPoolStatus, LiquiditySide
from app.domain.liquidity.ids import pool_id, zone_id
from app.domain.liquidity.models import (
    EqualHighs,
    EqualLows,
    LiquidityPool,
    LiquidityZone,
)
from app.domain.value_objects.market import Price


@dataclass(frozen=True, slots=True)
class ZoneBuildResult:
    """Immutable pools + zones produced from equal-level detections."""

    pools: tuple[LiquidityPool, ...]
    zones: tuple[LiquidityZone, ...]


@dataclass(frozen=True, slots=True)
class LiquidityZoneBuilder:
    """Build liquidity pools and zones from equal highs/lows."""

    zone_padding: Decimal = Decimal("0")

    def build(
        self,
        equal_highs: Sequence[EqualHighs],
        equal_lows: Sequence[EqualLows],
    ) -> ZoneBuildResult:
        """Create one pool + one zone per equal-level cluster."""
        pools: list[LiquidityPool] = []
        zones: list[LiquidityZone] = []

        for eqh in equal_highs:
            pool = self._pool_from_highs(eqh)
            pools.append(pool)
            zones.append(self._zone_for_pool(pool))

        for eql in equal_lows:
            pool = self._pool_from_lows(eql)
            pools.append(pool)
            zones.append(self._zone_for_pool(pool))

        return ZoneBuildResult(pools=tuple(pools), zones=tuple(zones))

    def _pool_from_highs(self, eqh: EqualHighs) -> LiquidityPool:
        first = min(eqh.bar_indices)
        last = max(eqh.bar_indices)
        formed = max(eqh.timestamps)
        symbol = str(eqh.symbol_code)
        return LiquidityPool(
            symbol_code=eqh.symbol_code,
            timeframe=eqh.timeframe,
            side=LiquiditySide.SELL_SIDE,
            price=eqh.price,
            strength=eqh.touch_count,
            first_bar_index=first,
            last_bar_index=last,
            formed_at=formed,
            status=LiquidityPoolStatus.ACTIVE,
            source_id=eqh.id,
            id=pool_id(
                symbol,
                eqh.timeframe.value,
                LiquiditySide.SELL_SIDE.value,
                str(eqh.price),
                first,
                last,
            ),
        )

    def _pool_from_lows(self, eql: EqualLows) -> LiquidityPool:
        first = min(eql.bar_indices)
        last = max(eql.bar_indices)
        formed = max(eql.timestamps)
        symbol = str(eql.symbol_code)
        return LiquidityPool(
            symbol_code=eql.symbol_code,
            timeframe=eql.timeframe,
            side=LiquiditySide.BUY_SIDE,
            price=eql.price,
            strength=eql.touch_count,
            first_bar_index=first,
            last_bar_index=last,
            formed_at=formed,
            status=LiquidityPoolStatus.ACTIVE,
            source_id=eql.id,
            id=pool_id(
                symbol,
                eql.timeframe.value,
                LiquiditySide.BUY_SIDE.value,
                str(eql.price),
                first,
                last,
            ),
        )

    def _zone_for_pool(self, pool: LiquidityPool) -> LiquidityZone:
        pad = self.zone_padding
        low = Price.of(pool.price.value - pad)
        high = Price.of(pool.price.value + pad)
        # Clamp low to non-negative Price invariant.
        if low.value < 0:
            low = Price.of(Decimal("0"))
        return LiquidityZone(
            symbol_code=pool.symbol_code,
            timeframe=pool.timeframe,
            side=pool.side,
            low_price=low,
            high_price=high,
            pools=(pool,),
            formed_at=pool.formed_at,
            id=zone_id(
                str(pool.symbol_code),
                pool.timeframe.value,
                pool.side.value,
                str(low),
                str(high),
            ),
        )
