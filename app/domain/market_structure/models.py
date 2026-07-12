"""Market structure entity models.

Immutable records describing swings, structure nodes, BOS/CHoCH events,
trend state, and point-in-time snapshots. Multi-symbol and multi-timeframe
ready via ``symbol_code`` + ``timeframe`` on every record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Self
from uuid import UUID, uuid4

from app.domain.entities._guards import require
from app.domain.market_data._validation import ensure_price, ensure_utc
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import (
    StructureBreakKind,
    StructureRole,
    SwingKind,
    TrendDirection,
)
from app.domain.value_objects.identity import SymbolCode
from app.domain.value_objects.market import Price


@dataclass(frozen=True, kw_only=True, slots=True)
class SwingPoint:
    """Immutable pivot high or low in a price series.

    Why it exists
    -------------
    Swing points are the atoms of market structure. They locate confirmed
    local extremes without computing oscillators or moving averages.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    kind: SwingKind
    price: Price
    bar_index: int
    timestamp: datetime
    id: UUID = field(default_factory=uuid4)
    strength: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "timestamp", ensure_utc(self.timestamp, field="timestamp")
        )
        require(self.bar_index >= 0, "bar_index must be non-negative")
        require(self.strength >= 1, "strength must be >= 1")
        require(
            isinstance(self.symbol_code, SymbolCode), "symbol_code must be SymbolCode"
        )
        require(isinstance(self.timeframe, Timeframe), "timeframe must be Timeframe")
        require(isinstance(self.price, Price), "price must be Price")

    @classmethod
    def create(
        cls,
        *,
        symbol_code: str | SymbolCode,
        timeframe: Timeframe | str,
        kind: SwingKind,
        price: Price | str | int,
        bar_index: int,
        timestamp: datetime,
        strength: int = 1,
        entity_id: UUID | None = None,
    ) -> Self:
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
        kwargs: dict[str, object] = {
            "symbol_code": code,
            "timeframe": tf,
            "kind": kind,
            "price": ensure_price(price, field="price"),
            "bar_index": bar_index,
            "timestamp": timestamp,
            "strength": strength,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "kind": self.kind.value,
            "price": str(self.price),
            "bar_index": self.bar_index,
            "timestamp": self.timestamp.isoformat(),
            "strength": self.strength,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class StructureNode:
    """A swing point annotated with its structural role (HH/HL/LH/LL).

    Why it exists
    -------------
    Connects raw swings into an ordered structure sequence used to infer
    trend and detect BOS / CHoCH.
    """

    swing: SwingPoint
    role: StructureRole
    sequence: int
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        require(self.sequence >= 0, "sequence must be non-negative")

    @property
    def symbol_code(self) -> SymbolCode:
        return self.swing.symbol_code

    @property
    def timeframe(self) -> Timeframe:
        return self.swing.timeframe

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "sequence": self.sequence,
            "role": self.role.value,
            "swing": self.swing.to_dict(),
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class TrendState:
    """Immutable qualitative trend classification for a symbol/timeframe.

    Why it exists
    -------------
    Captures the current structural bias (up / down / range) derived from
    swing roles — not from lagging indicators.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    direction: TrendDirection
    as_of: datetime
    last_structure_role: StructureRole = StructureRole.UNKNOWN
    swing_count: int = 0
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, field="as_of"))
        require(self.swing_count >= 0, "swing_count must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "direction": self.direction.value,
            "as_of": self.as_of.isoformat(),
            "last_structure_role": self.last_structure_role.value,
            "swing_count": self.swing_count,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class BreakOfStructure:
    """Immutable Break of Structure (BOS) — with-trend structural break.

    Why it exists
    -------------
    Records when price breaks a prior swing *in the direction of the trend*,
    confirming continuation of the existing structure. Not a trade signal.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    broken_swing: SwingPoint
    break_price: Price
    broken_at: datetime
    trend_direction: TrendDirection
    kind: StructureBreakKind = StructureBreakKind.BOS
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "broken_at", ensure_utc(self.broken_at, field="broken_at")
        )
        require(
            self.kind == StructureBreakKind.BOS,
            "BreakOfStructure.kind must be BOS",
        )
        require(
            self.broken_swing.symbol_code == self.symbol_code,
            "broken_swing symbol must match",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "kind": self.kind.value,
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "break_price": str(self.break_price),
            "broken_at": self.broken_at.isoformat(),
            "trend_direction": self.trend_direction.value,
            "broken_swing": self.broken_swing.to_dict(),
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class ChangeOfCharacter:
    """Immutable Change of Character (CHoCH) — against-trend structural break.

    Why it exists
    -------------
    Records when price breaks a prior swing *against* the prevailing trend,
    marking a potential character change in structure. Not a trade signal.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    broken_swing: SwingPoint
    break_price: Price
    broken_at: datetime
    previous_trend: TrendDirection
    kind: StructureBreakKind = StructureBreakKind.CHOCH
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "broken_at", ensure_utc(self.broken_at, field="broken_at")
        )
        require(
            self.kind == StructureBreakKind.CHOCH,
            "ChangeOfCharacter.kind must be CHOCH",
        )
        require(
            self.broken_swing.symbol_code == self.symbol_code,
            "broken_swing symbol must match",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "kind": self.kind.value,
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "break_price": str(self.break_price),
            "broken_at": self.broken_at.isoformat(),
            "previous_trend": self.previous_trend.value,
            "broken_swing": self.broken_swing.to_dict(),
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class StructureSnapshot:
    """Immutable point-in-time market-structure view for one symbol/timeframe.

    Why it exists
    -------------
    Bundles swings, structure nodes, trend, and the latest BOS/CHoCH into a
    single read-model-friendly record. Snapshots are immutable once built.
    """

    symbol_code: SymbolCode
    timeframe: Timeframe
    as_of: datetime
    swings: tuple[SwingPoint, ...]
    nodes: tuple[StructureNode, ...]
    trend: TrendState
    breaks_of_structure: tuple[BreakOfStructure, ...] = ()
    changes_of_character: tuple[ChangeOfCharacter, ...] = ()
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of, field="as_of"))
        for swing in self.swings:
            require(
                swing.symbol_code == self.symbol_code
                and swing.timeframe == self.timeframe,
                "swing must match snapshot symbol/timeframe",
            )
        for node in self.nodes:
            require(
                node.symbol_code == self.symbol_code
                and node.timeframe == self.timeframe,
                "node must match snapshot symbol/timeframe",
            )

    @property
    def latest_bos(self) -> BreakOfStructure | None:
        return self.breaks_of_structure[-1] if self.breaks_of_structure else None

    @property
    def latest_choch(self) -> ChangeOfCharacter | None:
        return self.changes_of_character[-1] if self.changes_of_character else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "timeframe": self.timeframe.value,
            "as_of": self.as_of.isoformat(),
            "trend": self.trend.to_dict(),
            "swings": [s.to_dict() for s in self.swings],
            "nodes": [n.to_dict() for n in self.nodes],
            "breaks_of_structure": [b.to_dict() for b in self.breaks_of_structure],
            "changes_of_character": [c.to_dict() for c in self.changes_of_character],
        }
