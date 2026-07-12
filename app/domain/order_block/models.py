"""Order-block entity models.

Immutable records for zones, blocks, breakers, mitigations, quality, and
snapshots. Multi-symbol / multi-timeframe ready. Not trade signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID, uuid4

from app.domain.entities._guards import require
from app.domain.market_data._validation import ensure_utc
from app.domain.market_data.timeframe import Timeframe
from app.domain.order_block.enums import (
    MitigationKind,
    OrderBlockOrigin,
    OrderBlockSide,
    OrderBlockState,
    QualityGrade,
)
from app.domain.value_objects.identity import SymbolCode
from app.domain.value_objects.market import Price

# Valid lifecycle transitions (from → frozenset[to]).
ORDER_BLOCK_TRANSITIONS: dict[OrderBlockState, frozenset[OrderBlockState]] = {
    OrderBlockState.DETECTED: frozenset(
        {OrderBlockState.VALIDATED, OrderBlockState.EXPIRED}
    ),
    OrderBlockState.VALIDATED: frozenset(
        {OrderBlockState.ACTIVE, OrderBlockState.EXPIRED}
    ),
    OrderBlockState.ACTIVE: frozenset(
        {
            OrderBlockState.MITIGATED,
            OrderBlockState.BREAKER,
            OrderBlockState.EXPIRED,
        }
    ),
    OrderBlockState.MITIGATED: frozenset(
        {OrderBlockState.BREAKER, OrderBlockState.EXPIRED}
    ),
    OrderBlockState.BREAKER: frozenset({OrderBlockState.EXPIRED}),
    OrderBlockState.EXPIRED: frozenset(),
}


@dataclass(frozen=True, kw_only=True, slots=True)
class OrderBlockZone:
    """Price band of an order block (candle range or body band).

    Why it exists
    -------------
    Separates geometric zone maths from lifecycle/state of the block itself.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    low_price: Price
    high_price: Price
    bar_index: int
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
        require(self.bar_index >= 0, "bar_index must be non-negative")

    @property
    def mid_price(self) -> Price:
        mid = (self.low_price.value + self.high_price.value) / Decimal("2")
        return Price.of(mid)

    @property
    def range_size(self) -> Decimal:
        return self.high_price.value - self.low_price.value

    def contains(self, price: Price | Decimal) -> bool:
        value = price.value if isinstance(price, Price) else price
        return self.low_price.value <= value <= self.high_price.value

    def overlaps_candle(self, low: Price, high: Price) -> bool:
        return not (
            high.value < self.low_price.value or low.value > self.high_price.value
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "low_price": str(self.low_price),
            "high_price": str(self.high_price),
            "bar_index": self.bar_index,
            "formed_at": self.formed_at.isoformat(),
            "range_size": str(self.range_size),
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class OrderBlockQuality:
    """Immutable quality metrics for an order block.

    Why it exists
    -------------
    Captures structural strength (displacement, freshness, confluence) as
    measurable facts — not an entry score or trade signal.
    """

    score: Decimal
    grade: QualityGrade
    displacement_ratio: Decimal = Decimal("0")
    freshness_bars: int = 0
    liquidity_confluence: bool = False
    unmitigated: bool = True
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        require(
            Decimal("0") <= self.score <= Decimal("100"),
            "score must be in [0, 100]",
        )
        require(self.freshness_bars >= 0, "freshness_bars must be non-negative")
        require(
            self.displacement_ratio >= 0,
            "displacement_ratio must be non-negative",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "score": str(self.score),
            "grade": self.grade.value,
            "displacement_ratio": str(self.displacement_ratio),
            "freshness_bars": self.freshness_bars,
            "liquidity_confluence": self.liquidity_confluence,
            "unmitigated": self.unmitigated,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class OrderBlock:
    """Immutable order block with lifecycle state.

    Why it exists
    -------------
    Records the last opposing candle before a structural displacement
    (BOS/CHoCH/impulse). Observational only — not a trade signal.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    side: OrderBlockSide
    zone: OrderBlockZone
    origin: OrderBlockOrigin
    state: OrderBlockState
    formed_at: datetime
    origin_bar_index: int
    displacement_bar_index: int
    quality: OrderBlockQuality | None = None
    source_event_id: UUID | None = None
    validated_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "formed_at", ensure_utc(self.formed_at, field="formed_at")
        )
        if self.validated_at is not None:
            object.__setattr__(
                self,
                "validated_at",
                ensure_utc(self.validated_at, field="validated_at"),
            )
        require(self.origin_bar_index >= 0, "origin_bar_index must be non-negative")
        require(
            self.displacement_bar_index >= self.origin_bar_index,
            "displacement_bar_index must be >= origin_bar_index",
        )
        require(
            self.zone.symbol_code == self.symbol_code
            and self.zone.timeframe == self.timeframe,
            "zone must match order block symbol/timeframe",
        )

    def transition(
        self, new_state: OrderBlockState, *, at: datetime | None = None
    ) -> Self:
        """Return a copy after a legal lifecycle transition."""
        allowed = ORDER_BLOCK_TRANSITIONS[self.state]
        require(
            new_state in allowed,
            f"illegal transition {self.state.value} → {new_state.value}",
            from_state=self.state.value,
            to_state=new_state.value,
        )
        validated_at = self.validated_at
        if new_state == OrderBlockState.VALIDATED and at is not None:
            validated_at = ensure_utc(at, field="validated_at")
        elif new_state == OrderBlockState.VALIDATED and validated_at is None:
            validated_at = self.formed_at
        return type(self)(
            symbol_code=self.symbol_code,
            timeframe=self.timeframe,
            side=self.side,
            zone=self.zone,
            origin=self.origin,
            state=new_state,
            formed_at=self.formed_at,
            origin_bar_index=self.origin_bar_index,
            displacement_bar_index=self.displacement_bar_index,
            quality=self.quality,
            source_event_id=self.source_event_id,
            validated_at=validated_at,
            id=self.id,
        )

    def with_quality(self, quality: OrderBlockQuality) -> Self:
        return type(self)(
            symbol_code=self.symbol_code,
            timeframe=self.timeframe,
            side=self.side,
            zone=self.zone,
            origin=self.origin,
            state=self.state,
            formed_at=self.formed_at,
            origin_bar_index=self.origin_bar_index,
            displacement_bar_index=self.displacement_bar_index,
            quality=quality,
            source_event_id=self.source_event_id,
            validated_at=self.validated_at,
            id=self.id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "side": self.side.value,
            "state": self.state.value,
            "origin": self.origin.value,
            "formed_at": self.formed_at.isoformat(),
            "origin_bar_index": self.origin_bar_index,
            "displacement_bar_index": self.displacement_bar_index,
            "source_event_id": (
                str(self.source_event_id) if self.source_event_id else None
            ),
            "validated_at": (
                self.validated_at.isoformat() if self.validated_at else None
            ),
            "zone": self.zone.to_dict(),
            "quality": self.quality.to_dict() if self.quality else None,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class BreakerBlock:
    """Order block that failed and flipped after opposing close-through.

    Why it exists
    -------------
    Records structural invalidation of an OB into a breaker. Not a signal.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    order_block: OrderBlock
    broken_at: datetime
    break_price: Price
    bar_index: int
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "broken_at", ensure_utc(self.broken_at, field="broken_at")
        )
        require(self.bar_index >= 0, "bar_index must be non-negative")
        require(
            self.order_block.symbol_code == self.symbol_code
            and self.order_block.timeframe == self.timeframe,
            "order_block must match breaker symbol/timeframe",
        )
        require(
            self.order_block.state == OrderBlockState.BREAKER,
            "breaker source block must be in BREAKER state",
        )

    @property
    def side(self) -> OrderBlockSide:
        return self.order_block.side

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "broken_at": self.broken_at.isoformat(),
            "break_price": str(self.break_price),
            "bar_index": self.bar_index,
            "order_block": self.order_block.to_dict(),
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class MitigationBlock:
    """Record of price revisiting an order-block zone.

    Why it exists
    -------------
    Tracks mitigation depth as a structural fact for lifecycle — not an entry.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    order_block: OrderBlock
    kind: MitigationKind
    mitigated_at: datetime
    touch_price: Price
    bar_index: int
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "mitigated_at", ensure_utc(self.mitigated_at, field="mitigated_at")
        )
        require(self.bar_index >= 0, "bar_index must be non-negative")
        require(
            self.order_block.symbol_code == self.symbol_code
            and self.order_block.timeframe == self.timeframe,
            "order_block must match mitigation symbol/timeframe",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "kind": self.kind.value,
            "mitigated_at": self.mitigated_at.isoformat(),
            "touch_price": str(self.touch_price),
            "bar_index": self.bar_index,
            "order_block": self.order_block.to_dict(),
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class OrderBlockSnapshot:
    """Immutable point-in-time order-block view for one symbol/timeframe.

    Why it exists
    -------------
    Bundles blocks, breakers, mitigations into one read-model record.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    as_of: datetime
    order_blocks: tuple[OrderBlock, ...]
    breakers: tuple[BreakerBlock, ...] = ()
    mitigations: tuple[MitigationBlock, ...] = ()
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, field="as_of"))
        for block in self.order_blocks:
            require(
                block.symbol_code == self.symbol_code
                and block.timeframe == self.timeframe,
                "order block must match snapshot symbol/timeframe",
            )

    @property
    def active_blocks(self) -> tuple[OrderBlock, ...]:
        return tuple(b for b in self.order_blocks if b.state == OrderBlockState.ACTIVE)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "as_of": self.as_of.isoformat(),
            "order_blocks": [b.to_dict() for b in self.order_blocks],
            "breakers": [b.to_dict() for b in self.breakers],
            "mitigations": [m.to_dict() for m in self.mitigations],
        }
