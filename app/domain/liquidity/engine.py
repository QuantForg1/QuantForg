"""LiquidityEngine — orchestrate equals → pools/zones → sweeps → snapshot.

Why it exists
-------------
Single entry point that loads price/swing (and optional structure) context,
detects equal highs/lows, builds pools/zones, detects sweeps, classifies
liquidity state, and returns an immutable :class:`LiquiditySnapshot` plus
domain events. Does not trade, call MetaTrader, run AI, or emit signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.events.base import DomainEvent
from app.domain.events.liquidity import (
    LiquidityPoolDetected,
    LiquidityStateChanged,
    LiquiditySweepDetected,
    LiquidityZoneCreated,
)
from app.domain.interfaces.liquidity import (
    LiquidityRepositoryPort,
    MarketStructurePort,
    PriceHistoryPort,
    SwingProviderPort,
)
from app.domain.liquidity.enums import (
    LiquidityPoolStatus,
    LiquiditySide,
    LiquidityStateKind,
)
from app.domain.liquidity.equal_high_detector import EqualHighDetector
from app.domain.liquidity.equal_low_detector import EqualLowDetector
from app.domain.liquidity.models import (
    LiquidityPool,
    LiquiditySnapshot,
    LiquidityState,
    LiquiditySweep,
    LiquidityZone,
)
from app.domain.liquidity.sweep_detector import LiquiditySweepDetector
from app.domain.liquidity.zone_builder import LiquidityZoneBuilder
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode


@dataclass(frozen=True, slots=True)
class LiquidityResult:
    """Engine output: immutable snapshot plus pending domain events."""

    snapshot: LiquiditySnapshot
    events: tuple[DomainEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class LiquidityEngine:
    """Orchestrate liquidity analysis for one symbol/timeframe."""

    prices: PriceHistoryPort
    swings: SwingProviderPort
    structure: MarketStructurePort | None = None
    repository: LiquidityRepositoryPort | None = None
    equal_highs: EqualHighDetector = field(
        default_factory=lambda: EqualHighDetector(tolerance=Decimal("0"))
    )
    equal_lows: EqualLowDetector = field(
        default_factory=lambda: EqualLowDetector(tolerance=Decimal("0"))
    )
    zones: LiquidityZoneBuilder = field(default_factory=LiquidityZoneBuilder)
    sweeps: LiquiditySweepDetector = field(default_factory=LiquiditySweepDetector)
    swing_left: int = 2
    swing_right: int = 2
    candle_limit: int = 500

    async def analyze(
        self,
        symbol_code: str | SymbolCode,
        timeframe: Timeframe | str,
        *,
        persist: bool = False,
        as_of: datetime | None = None,
    ) -> LiquidityResult:
        """Run a full liquidity analysis pass and return snapshot + events."""
        code = (
            symbol_code
            if isinstance(symbol_code, SymbolCode)
            else SymbolCode(value=symbol_code)
        )
        tf = (
            timeframe
            if isinstance(timeframe, Timeframe)
            else Timeframe.parse(timeframe)
        )
        moment = as_of or datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)

        candles = await self.prices.get_candles(code, tf, limit=self.candle_limit)
        swing_points = await self.swings.get_swings(
            code,
            tf,
            left=self.swing_left,
            right=self.swing_right,
            limit=self.candle_limit,
        )

        # Optional structure context — reserved for future enrichment; loaded
        # so adapters are exercised without coupling analysis to trend.
        if self.structure is not None:
            await self.structure.get_latest_snapshot(code, tf)

        eq_highs = self.equal_highs.detect(swing_points)
        eq_lows = self.equal_lows.detect(swing_points)
        built = self.zones.build(eq_highs, eq_lows)
        sweep_result = self.sweeps.detect(built.pools, candles)

        # Refresh zone pool references to swept status.
        pools = sweep_result.pools
        zones = self._zones_with_pools(built.zones, pools)
        state = self._classify_state(
            code,
            tf,
            moment,
            pools=pools,
            sweeps=sweep_result.sweeps,
        )

        snapshot = LiquiditySnapshot(
            symbol_code=code,
            timeframe=tf,
            as_of=moment,
            equal_highs=eq_highs,
            equal_lows=eq_lows,
            pools=pools,
            zones=zones,
            sweeps=sweep_result.sweeps,
            state=state,
        )

        previous: LiquiditySnapshot | None = None
        if self.repository is not None:
            previous = await self.repository.get_latest_snapshot(code, tf)

        events = self._build_events(snapshot, previous)

        if persist and self.repository is not None:
            await self.repository.save_snapshot(snapshot)

        return LiquidityResult(snapshot=snapshot, events=tuple(events))

    @staticmethod
    def _zones_with_pools(
        zones: tuple[LiquidityZone, ...],
        pools: tuple[LiquidityPool, ...],
    ) -> tuple[LiquidityZone, ...]:
        by_id = {p.id: p for p in pools}
        refreshed: list[LiquidityZone] = []
        for zone in zones:
            new_pools = tuple(by_id.get(p.id, p) for p in zone.pools)
            refreshed.append(
                LiquidityZone(
                    symbol_code=zone.symbol_code,
                    timeframe=zone.timeframe,
                    side=zone.side,
                    low_price=zone.low_price,
                    high_price=zone.high_price,
                    pools=new_pools,
                    formed_at=zone.formed_at,
                    id=zone.id,
                )
            )
        return tuple(refreshed)

    @staticmethod
    def _classify_state(
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        as_of: datetime,
        *,
        pools: tuple[LiquidityPool, ...],
        sweeps: tuple[LiquiditySweep, ...],
    ) -> LiquidityState:
        active_buy = sum(
            1
            for p in pools
            if p.side == LiquiditySide.BUY_SIDE
            and p.status == LiquidityPoolStatus.ACTIVE
        )
        active_sell = sum(
            1
            for p in pools
            if p.side == LiquiditySide.SELL_SIDE
            and p.status == LiquidityPoolStatus.ACTIVE
        )
        swept_buy = sum(
            1
            for p in pools
            if p.side == LiquiditySide.BUY_SIDE
            and p.status == LiquidityPoolStatus.SWEPT
        )
        swept_sell = sum(
            1
            for p in pools
            if p.side == LiquiditySide.SELL_SIDE
            and p.status == LiquidityPoolStatus.SWEPT
        )
        last_kind = sweeps[-1].kind if sweeps else None

        if not pools:
            kind = LiquidityStateKind.UNKNOWN
        elif last_kind is not None and swept_sell > swept_buy and active_sell == 0:
            kind = LiquidityStateKind.SELL_SIDE_SWEPT
        elif last_kind is not None and swept_buy > swept_sell and active_buy == 0:
            kind = LiquidityStateKind.BUY_SIDE_SWEPT
        elif active_buy > active_sell:
            kind = LiquidityStateKind.BUY_SIDE_HEAVY
        elif active_sell > active_buy:
            kind = LiquidityStateKind.SELL_SIDE_HEAVY
        else:
            kind = LiquidityStateKind.BALANCED

        return LiquidityState(
            symbol_code=symbol_code,
            timeframe=timeframe,
            kind=kind,
            as_of=as_of,
            active_buy_pools=active_buy,
            active_sell_pools=active_sell,
            swept_buy_pools=swept_buy,
            swept_sell_pools=swept_sell,
            last_sweep_kind=last_kind,
        )

    def _build_events(
        self,
        snapshot: LiquiditySnapshot,
        previous: LiquiditySnapshot | None,
    ) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        prev_pools = {p.id for p in previous.pools} if previous else set()
        prev_zones = {z.id for z in previous.zones} if previous else set()
        prev_sweeps = {s.id for s in previous.sweeps} if previous else set()

        for pool in snapshot.pools:
            if pool.id in prev_pools:
                continue
            events.append(
                LiquidityPoolDetected(
                    pool_id=pool.id,
                    symbol_code=str(pool.symbol_code),
                    timeframe=pool.timeframe.value,
                    side=pool.side.value,
                    price=str(pool.price),
                    strength=pool.strength,
                    occurred_at=pool.formed_at,
                )
            )

        for zone in snapshot.zones:
            if zone.id in prev_zones:
                continue
            events.append(
                LiquidityZoneCreated(
                    zone_id=zone.id,
                    symbol_code=str(zone.symbol_code),
                    timeframe=zone.timeframe.value,
                    side=zone.side.value,
                    low_price=str(zone.low_price),
                    high_price=str(zone.high_price),
                    pool_count=len(zone.pools),
                    occurred_at=zone.formed_at,
                )
            )

        for sweep in snapshot.sweeps:
            if sweep.id in prev_sweeps:
                continue
            events.append(
                LiquiditySweepDetected(
                    sweep_id=sweep.id,
                    symbol_code=str(sweep.symbol_code),
                    timeframe=sweep.timeframe.value,
                    kind=sweep.kind.value,
                    pool_id=sweep.pool.id,
                    sweep_price=str(sweep.sweep_price),
                    occurred_at=sweep.swept_at,
                )
            )

        if previous is None or previous.state.kind != snapshot.state.kind:
            prev_kind = previous.state.kind.value if previous is not None else "unknown"
            events.append(
                LiquidityStateChanged(
                    symbol_code=str(snapshot.symbol_code),
                    timeframe=snapshot.timeframe.value,
                    previous_kind=prev_kind,
                    current_kind=snapshot.state.kind.value,
                    state_id=snapshot.state.id,
                    occurred_at=snapshot.as_of,
                )
            )

        return events
