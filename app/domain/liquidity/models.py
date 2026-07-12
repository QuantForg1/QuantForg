"""Liquidity engine entity models.

Immutable records for equal highs/lows, pools, zones, sweeps, state, and
snapshots. Multi-symbol and multi-timeframe ready via ``symbol_code`` +
``timeframe``. Not trade signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID, uuid4

from app.domain.entities._guards import require
from app.domain.liquidity.enums import (
    LiquidityPoolStatus,
    LiquiditySide,
    LiquidityStateKind,
    SweepKind,
)
from app.domain.market_data._validation import ensure_utc
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode
from app.domain.value_objects.market import Price


@dataclass(frozen=True, kw_only=True, slots=True)
class EqualHighs:
    """Two or more swing highs at (near) the same price — sell-side liquidity.

    Why it exists
    -------------
    Equal highs mark resting sell-side liquidity above price. A structural
    observation only — not an entry signal.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    price: Price
    bar_indices: tuple[int, ...]
    timestamps: tuple[datetime, ...]
    tolerance: Decimal = Decimal("0")
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "timestamps",
            tuple(ensure_utc(t, field="timestamps") for t in self.timestamps),
        )
        require(len(self.bar_indices) >= 2, "EqualHighs requires >= 2 bars")
        require(
            len(self.bar_indices) == len(self.timestamps),
            "bar_indices and timestamps length must match",
        )
        require(self.tolerance >= 0, "tolerance must be non-negative")

    @property
    def touch_count(self) -> int:
        return len(self.bar_indices)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "price": str(self.price),
            "bar_indices": list(self.bar_indices),
            "timestamps": [t.isoformat() for t in self.timestamps],
            "tolerance": str(self.tolerance),
            "touch_count": self.touch_count,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class EqualLows:
    """Two or more swing lows at (near) the same price — buy-side liquidity.

    Why it exists
    -------------
    Equal lows mark resting buy-side liquidity below price. Structural only.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    price: Price
    bar_indices: tuple[int, ...]
    timestamps: tuple[datetime, ...]
    tolerance: Decimal = Decimal("0")
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "timestamps",
            tuple(ensure_utc(t, field="timestamps") for t in self.timestamps),
        )
        require(len(self.bar_indices) >= 2, "EqualLows requires >= 2 bars")
        require(
            len(self.bar_indices) == len(self.timestamps),
            "bar_indices and timestamps length must match",
        )
        require(self.tolerance >= 0, "tolerance must be non-negative")

    @property
    def touch_count(self) -> int:
        return len(self.bar_indices)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "price": str(self.price),
            "bar_indices": list(self.bar_indices),
            "timestamps": [t.isoformat() for t in self.timestamps],
            "tolerance": str(self.tolerance),
            "touch_count": self.touch_count,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class LiquidityPool:
    """Resting liquidity concentration at a price level.

    Why it exists
    -------------
    Normalises equal highs/lows (and future sources) into a single pool
    abstraction the engine can track and sweep-detect against.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    side: LiquiditySide
    price: Price
    strength: int
    first_bar_index: int
    last_bar_index: int
    formed_at: datetime
    status: LiquidityPoolStatus = LiquidityPoolStatus.ACTIVE
    source_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "formed_at", ensure_utc(self.formed_at, field="formed_at")
        )
        require(self.strength >= 2, "pool strength must be >= 2")
        require(self.first_bar_index >= 0, "first_bar_index must be non-negative")
        require(
            self.last_bar_index >= self.first_bar_index,
            "last_bar_index must be >= first_bar_index",
        )

    def with_status(self, status: LiquidityPoolStatus) -> Self:
        """Return a copy with updated status (snapshots stay immutable)."""
        return type(self)(
            symbol_code=self.symbol_code,
            timeframe=self.timeframe,
            side=self.side,
            price=self.price,
            strength=self.strength,
            first_bar_index=self.first_bar_index,
            last_bar_index=self.last_bar_index,
            formed_at=self.formed_at,
            status=status,
            source_id=self.source_id,
            id=self.id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "side": self.side.value,
            "price": str(self.price),
            "strength": self.strength,
            "first_bar_index": self.first_bar_index,
            "last_bar_index": self.last_bar_index,
            "formed_at": self.formed_at.isoformat(),
            "status": self.status.value,
            "source_id": str(self.source_id) if self.source_id else None,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class LiquidityZone:
    """Price band aggregating one or more pools on the same side.

    Why it exists
    -------------
    Groups nearby pools into a zone for multi-touch liquidity areas without
    inventing trade entries.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    side: LiquiditySide
    low_price: Price
    high_price: Price
    pools: tuple[LiquidityPool, ...]
    formed_at: datetime
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "formed_at", ensure_utc(self.formed_at, field="formed_at")
        )
        require(
            self.high_price.value >= self.low_price.value,
            "high_price must be >= low_price",
        )
        require(len(self.pools) >= 1, "zone requires >= 1 pool")
        for pool in self.pools:
            require(
                pool.symbol_code == self.symbol_code
                and pool.timeframe == self.timeframe
                and pool.side == self.side,
                "pool must match zone symbol/timeframe/side",
            )

    @property
    def mid_price(self) -> Price:
        mid = (self.low_price.value + self.high_price.value) / Decimal("2")
        return Price.of(mid)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "side": self.side.value,
            "low_price": str(self.low_price),
            "high_price": str(self.high_price),
            "formed_at": self.formed_at.isoformat(),
            "pools": [p.to_dict() for p in self.pools],
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class LiquiditySweep:
    """Structural fact that price took a liquidity pool (wick through + reclaim).

    Why it exists
    -------------
    Records when a pool was swept. This is a market-structure liquidity fact,
    not a buy/sell signal.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    pool: LiquidityPool
    kind: SweepKind
    sweep_price: Price
    close_price: Price
    bar_index: int
    swept_at: datetime
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "swept_at", ensure_utc(self.swept_at, field="swept_at")
        )
        require(self.bar_index >= 0, "bar_index must be non-negative")
        require(
            self.pool.symbol_code == self.symbol_code
            and self.pool.timeframe == self.timeframe,
            "pool must match sweep symbol/timeframe",
        )
        if self.kind == SweepKind.HIGH_SWEEP:
            require(
                self.pool.side == LiquiditySide.SELL_SIDE,
                "high sweep must target sell-side pool",
            )
        else:
            require(
                self.pool.side == LiquiditySide.BUY_SIDE,
                "low sweep must target buy-side pool",
            )

    @property
    def side(self) -> LiquiditySide:
        return self.pool.side

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "kind": self.kind.value,
            "sweep_price": str(self.sweep_price),
            "close_price": str(self.close_price),
            "bar_index": self.bar_index,
            "swept_at": self.swept_at.isoformat(),
            "pool": self.pool.to_dict(),
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class LiquidityState:
    """Immutable qualitative liquidity state for a symbol/timeframe.

    Why it exists
    -------------
    Summarises active pools and recent sweeps into a single bias label —
    not an indicator and not a trade signal.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    kind: LiquidityStateKind
    as_of: datetime
    active_buy_pools: int = 0
    active_sell_pools: int = 0
    swept_buy_pools: int = 0
    swept_sell_pools: int = 0
    last_sweep_kind: SweepKind | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, field="as_of"))
        require(self.active_buy_pools >= 0, "active_buy_pools must be non-negative")
        require(self.active_sell_pools >= 0, "active_sell_pools must be non-negative")
        require(self.swept_buy_pools >= 0, "swept_buy_pools must be non-negative")
        require(self.swept_sell_pools >= 0, "swept_sell_pools must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "kind": self.kind.value,
            "as_of": self.as_of.isoformat(),
            "active_buy_pools": self.active_buy_pools,
            "active_sell_pools": self.active_sell_pools,
            "swept_buy_pools": self.swept_buy_pools,
            "swept_sell_pools": self.swept_sell_pools,
            "last_sweep_kind": (
                self.last_sweep_kind.value if self.last_sweep_kind else None
            ),
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class LiquiditySnapshot:
    """Immutable point-in-time liquidity view for one symbol/timeframe.

    Why it exists
    -------------
    Bundles equals, pools, zones, sweeps, and state into one read-model
    record. Snapshots are immutable once built.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    as_of: datetime
    equal_highs: tuple[EqualHighs, ...]
    equal_lows: tuple[EqualLows, ...]
    pools: tuple[LiquidityPool, ...]
    zones: tuple[LiquidityZone, ...]
    sweeps: tuple[LiquiditySweep, ...]
    state: LiquidityState
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, field="as_of"))
        for pool in self.pools:
            require(
                pool.symbol_code == self.symbol_code
                and pool.timeframe == self.timeframe,
                "pool must match snapshot symbol/timeframe",
            )
        for zone in self.zones:
            require(
                zone.symbol_code == self.symbol_code
                and zone.timeframe == self.timeframe,
                "zone must match snapshot symbol/timeframe",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "as_of": self.as_of.isoformat(),
            "state": self.state.to_dict(),
            "equal_highs": [e.to_dict() for e in self.equal_highs],
            "equal_lows": [e.to_dict() for e in self.equal_lows],
            "pools": [p.to_dict() for p in self.pools],
            "zones": [z.to_dict() for z in self.zones],
            "sweeps": [s.to_dict() for s in self.sweeps],
        }
