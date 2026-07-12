"""Fair Value Gap entity models.

Immutable records for zones, gaps, fills, lifecycle, quality, and snapshots.
Multi-symbol / multi-timeframe ready. Not trade signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID, uuid4

from app.domain.entities._guards import require
from app.domain.fair_value_gap.enums import (
    FairValueGapSide,
    FairValueGapState,
    FillKind,
    QualityGrade,
)
from app.domain.market_data._validation import ensure_utc
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode
from app.domain.value_objects.market import Price

# Valid lifecycle transitions (from → frozenset[to]).
GAP_TRANSITIONS: dict[FairValueGapState, frozenset[FairValueGapState]] = {
    FairValueGapState.DETECTED: frozenset(
        {FairValueGapState.ACTIVE, FairValueGapState.EXPIRED}
    ),
    FairValueGapState.ACTIVE: frozenset(
        {
            FairValueGapState.PARTIALLY_FILLED,
            FairValueGapState.FILLED,
            FairValueGapState.INVALIDATED,
            FairValueGapState.EXPIRED,
        }
    ),
    FairValueGapState.PARTIALLY_FILLED: frozenset(
        {
            FairValueGapState.FILLED,
            FairValueGapState.INVALIDATED,
            FairValueGapState.EXPIRED,
        }
    ),
    FairValueGapState.FILLED: frozenset({FairValueGapState.EXPIRED}),
    FairValueGapState.INVALIDATED: frozenset({FairValueGapState.EXPIRED}),
    FairValueGapState.EXPIRED: frozenset(),
}


@dataclass(frozen=True, kw_only=True, slots=True)
class FairValueGapZone:
    """Price band of the unfilled imbalance between candles i-2 and i.

    Why it exists
    -------------
    Separates geometric gap maths from lifecycle state of the FVG itself.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    low_price: Price
    high_price: Price
    middle_bar_index: int
    formed_at: datetime
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "formed_at", ensure_utc(self.formed_at, field="formed_at")
        )
        require(
            self.high_price.value > self.low_price.value,
            "FVG zone requires positive range (high > low)",
        )
        require(self.middle_bar_index >= 1, "middle_bar_index must be >= 1")

    @property
    def mid_price(self) -> Price:
        mid = (self.low_price.value + self.high_price.value) / Decimal("2")
        return Price.of(mid)

    @property
    def size(self) -> Decimal:
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
            "middle_bar_index": self.middle_bar_index,
            "formed_at": self.formed_at.isoformat(),
            "size": str(self.size),
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class GapLifecycle:
    """Immutable lifecycle record for a fair value gap.

    Why it exists
    -------------
    Captures state machine position and timestamps without mutating the gap.
    """

    state: FairValueGapState
    detected_at: datetime
    updated_at: datetime
    fill_ratio: Decimal = Decimal("0")
    activated_at: datetime | None = None
    filled_at: datetime | None = None
    invalidated_at: datetime | None = None
    expired_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "detected_at", ensure_utc(self.detected_at, field="detected_at")
        )
        object.__setattr__(
            self, "updated_at", ensure_utc(self.updated_at, field="updated_at")
        )
        for name in (
            "activated_at",
            "filled_at",
            "invalidated_at",
            "expired_at",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, ensure_utc(value, field=name))
        require(
            Decimal("0") <= self.fill_ratio <= Decimal("1"),
            "fill_ratio must be in [0, 1]",
        )

    def transition(
        self,
        new_state: FairValueGapState,
        *,
        at: datetime,
        fill_ratio: Decimal | None = None,
    ) -> Self:
        """Return a copy after a legal lifecycle transition."""
        allowed = GAP_TRANSITIONS[self.state]
        require(
            new_state in allowed,
            f"illegal gap transition {self.state.value} → {new_state.value}",
            from_state=self.state.value,
            to_state=new_state.value,
        )
        ratio = self.fill_ratio if fill_ratio is None else fill_ratio
        require(
            Decimal("0") <= ratio <= Decimal("1"),
            "fill_ratio must be in [0, 1]",
        )
        moment = ensure_utc(at, field="at")
        activated_at = self.activated_at
        filled_at = self.filled_at
        invalidated_at = self.invalidated_at
        expired_at = self.expired_at
        if new_state == FairValueGapState.ACTIVE and activated_at is None:
            activated_at = moment
        if new_state == FairValueGapState.FILLED:
            filled_at = moment
            ratio = Decimal("1")
        if new_state == FairValueGapState.INVALIDATED:
            invalidated_at = moment
        if new_state == FairValueGapState.EXPIRED:
            expired_at = moment
        return type(self)(
            state=new_state,
            detected_at=self.detected_at,
            updated_at=moment,
            fill_ratio=ratio,
            activated_at=activated_at,
            filled_at=filled_at,
            invalidated_at=invalidated_at,
            expired_at=expired_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "detected_at": self.detected_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "fill_ratio": str(self.fill_ratio),
            "activated_at": (
                self.activated_at.isoformat() if self.activated_at else None
            ),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "invalidated_at": (
                self.invalidated_at.isoformat() if self.invalidated_at else None
            ),
            "expired_at": self.expired_at.isoformat() if self.expired_at else None,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class GapQuality:
    """Immutable quality metrics for a fair value gap.

    Why it exists
    -------------
    Descriptive strength (size, displacement, confluence, freshness) —
    not an entry score or trade signal.
    """

    score: Decimal
    grade: QualityGrade
    size_ratio: Decimal = Decimal("0")
    freshness_bars: int = 0
    order_block_confluence: bool = False
    unfilled: bool = True
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        require(
            Decimal("0") <= self.score <= Decimal("100"),
            "score must be in [0, 100]",
        )
        require(self.freshness_bars >= 0, "freshness_bars must be non-negative")
        require(self.size_ratio >= 0, "size_ratio must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "score": str(self.score),
            "grade": self.grade.value,
            "size_ratio": str(self.size_ratio),
            "freshness_bars": self.freshness_bars,
            "order_block_confluence": self.order_block_confluence,
            "unfilled": self.unfilled,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class FairValueGap:
    """Immutable three-candle fair value gap with lifecycle.

    Why it exists
    -------------
    Records a price imbalance between candle i-2 and candle i around an
    impulsive middle candle. Observational only — not a trade signal.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    side: FairValueGapSide
    zone: FairValueGapZone
    lifecycle: GapLifecycle
    left_bar_index: int
    middle_bar_index: int
    right_bar_index: int
    quality: GapQuality | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        require(self.left_bar_index >= 0, "left_bar_index must be non-negative")
        require(
            self.middle_bar_index == self.left_bar_index + 1,
            "middle_bar_index must be left_bar_index + 1",
        )
        require(
            self.right_bar_index == self.middle_bar_index + 1,
            "right_bar_index must be middle_bar_index + 1",
        )
        require(
            self.zone.symbol_code == self.symbol_code
            and self.zone.timeframe == self.timeframe,
            "zone must match gap symbol/timeframe",
        )
        require(
            self.zone.middle_bar_index == self.middle_bar_index,
            "zone middle_bar_index must match gap",
        )

    @property
    def state(self) -> FairValueGapState:
        return self.lifecycle.state

    def with_lifecycle(self, lifecycle: GapLifecycle) -> Self:
        return type(self)(
            symbol_code=self.symbol_code,
            timeframe=self.timeframe,
            side=self.side,
            zone=self.zone,
            lifecycle=lifecycle,
            left_bar_index=self.left_bar_index,
            middle_bar_index=self.middle_bar_index,
            right_bar_index=self.right_bar_index,
            quality=self.quality,
            id=self.id,
        )

    def transition(
        self,
        new_state: FairValueGapState,
        *,
        at: datetime,
        fill_ratio: Decimal | None = None,
    ) -> Self:
        return self.with_lifecycle(
            self.lifecycle.transition(new_state, at=at, fill_ratio=fill_ratio)
        )

    def with_quality(self, quality: GapQuality) -> Self:
        return type(self)(
            symbol_code=self.symbol_code,
            timeframe=self.timeframe,
            side=self.side,
            zone=self.zone,
            lifecycle=self.lifecycle,
            left_bar_index=self.left_bar_index,
            middle_bar_index=self.middle_bar_index,
            right_bar_index=self.right_bar_index,
            quality=quality,
            id=self.id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "side": self.side.value,
            "left_bar_index": self.left_bar_index,
            "middle_bar_index": self.middle_bar_index,
            "right_bar_index": self.right_bar_index,
            "zone": self.zone.to_dict(),
            "lifecycle": self.lifecycle.to_dict(),
            "quality": self.quality.to_dict() if self.quality else None,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class GapFill:
    """Record of price filling (partially or fully) a fair value gap.

    Why it exists
    -------------
    Tracks fill depth as a structural fact for lifecycle — not an entry.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    gap: FairValueGap
    kind: FillKind
    fill_ratio: Decimal
    fill_price: Price
    bar_index: int
    filled_at: datetime
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "filled_at", ensure_utc(self.filled_at, field="filled_at")
        )
        require(self.bar_index >= 0, "bar_index must be non-negative")
        require(
            Decimal("0") < self.fill_ratio <= Decimal("1"),
            "fill_ratio must be in (0, 1]",
        )
        require(
            self.gap.symbol_code == self.symbol_code
            and self.gap.timeframe == self.timeframe,
            "gap must match fill symbol/timeframe",
        )
        if self.kind == FillKind.FULL:
            require(self.fill_ratio == Decimal("1"), "full fill requires ratio 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "kind": self.kind.value,
            "fill_ratio": str(self.fill_ratio),
            "fill_price": str(self.fill_price),
            "bar_index": self.bar_index,
            "filled_at": self.filled_at.isoformat(),
            "gap": self.gap.to_dict(),
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class FairValueGapSnapshot:
    """Immutable point-in-time FVG view for one symbol/timeframe.

    Why it exists
    -------------
    Bundles gaps and fills into one read-model record.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    as_of: datetime
    gaps: tuple[FairValueGap, ...]
    fills: tuple[GapFill, ...] = ()
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, field="as_of"))
        for gap in self.gaps:
            require(
                gap.symbol_code == self.symbol_code and gap.timeframe == self.timeframe,
                "gap must match snapshot symbol/timeframe",
            )

    @property
    def active_gaps(self) -> tuple[FairValueGap, ...]:
        return tuple(
            g
            for g in self.gaps
            if g.state
            in {
                FairValueGapState.ACTIVE,
                FairValueGapState.PARTIALLY_FILLED,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "as_of": self.as_of.isoformat(),
            "gaps": [g.to_dict() for g in self.gaps],
            "fills": [f.to_dict() for f in self.fills],
        }
