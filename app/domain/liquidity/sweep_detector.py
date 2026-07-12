"""LiquiditySweepDetector — detect structural pool sweeps.

Why it exists
-------------
A sell-side (equal-high) pool is swept when a later bar's high trades above
the pool and the close reclaims below. A buy-side pool is swept when a later
bar's low trades below the pool and the close reclaims above.

These are liquidity facts, not trade signals.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.liquidity.enums import (
    LiquidityPoolStatus,
    LiquiditySide,
    SweepKind,
)
from app.domain.liquidity.ids import sweep_id
from app.domain.liquidity.models import LiquidityPool, LiquiditySweep
from app.domain.market_data.candle import Candle


@dataclass(frozen=True, slots=True)
class SweepDetectionResult:
    """Sweeps plus pools with updated swept status."""

    sweeps: tuple[LiquiditySweep, ...]
    pools: tuple[LiquidityPool, ...]


@dataclass(frozen=True, slots=True)
class LiquiditySweepDetector:
    """Detect wick-through + reclaim sweeps of active pools."""

    def detect(
        self,
        pools: Sequence[LiquidityPool],
        candles: Sequence[Candle],
    ) -> SweepDetectionResult:
        """Return sweeps and status-updated pools (one sweep per pool max)."""
        if not pools or not candles:
            return SweepDetectionResult(sweeps=(), pools=tuple(pools))

        sweeps: list[LiquiditySweep] = []
        updated: list[LiquidityPool] = []

        for pool in pools:
            if pool.status == LiquidityPoolStatus.SWEPT:
                updated.append(pool)
                continue
            sweep = self._find_sweep(pool, candles)
            if sweep is None:
                updated.append(pool)
                continue
            sweeps.append(sweep)
            updated.append(pool.with_status(LiquidityPoolStatus.SWEPT))

        return SweepDetectionResult(
            sweeps=tuple(sweeps),
            pools=tuple(updated),
        )

    def _find_sweep(
        self,
        pool: LiquidityPool,
        candles: Sequence[Candle],
    ) -> LiquiditySweep | None:
        level = pool.price.value
        for index, candle in enumerate(candles):
            if index <= pool.last_bar_index:
                continue

            if pool.side == LiquiditySide.SELL_SIDE:
                if candle.high.value > level and candle.close.value < level:
                    return LiquiditySweep(
                        symbol_code=pool.symbol_code,
                        timeframe=pool.timeframe,
                        pool=pool.with_status(LiquidityPoolStatus.SWEPT),
                        kind=SweepKind.HIGH_SWEEP,
                        sweep_price=candle.high,
                        close_price=candle.close,
                        bar_index=index,
                        swept_at=candle.close_time,
                        id=sweep_id(pool.id, index),
                    )
            else:
                if candle.low.value < level and candle.close.value > level:
                    return LiquiditySweep(
                        symbol_code=pool.symbol_code,
                        timeframe=pool.timeframe,
                        pool=pool.with_status(LiquidityPoolStatus.SWEPT),
                        kind=SweepKind.LOW_SWEEP,
                        sweep_price=candle.low,
                        close_price=candle.close,
                        bar_index=index,
                        swept_at=candle.close_time,
                        id=sweep_id(pool.id, index),
                    )
        return None
