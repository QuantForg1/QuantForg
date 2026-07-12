"""Candle — OHLCV bar for a symbol and timeframe.

Why it exists
-------------
A Candle (bar) aggregates price action over a fixed timeframe window. It is
historical market metadata used later for charting and analysis. This model
stores OHLCV only — it does **not** compute indicators or run strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID, uuid4

from app.domain.entities._guards import require
from app.domain.market_data._validation import (
    ensure_non_negative_decimal,
    ensure_price,
    ensure_utc,
)
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode
from app.domain.value_objects.market import Price


@dataclass(frozen=True, kw_only=True, slots=True)
class Candle:
    """Immutable OHLCV candle for one symbol and timeframe."""

    symbol_code: SymbolCode
    timeframe: Timeframe
    open_time: datetime
    close_time: datetime
    open: Price
    high: Price
    low: Price
    close: Price
    volume: Decimal = Decimal("0")
    id: UUID = field(default_factory=uuid4)
    symbol_id: UUID | None = None
    tick_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "open_time", ensure_utc(self.open_time, field="open_time")
        )
        object.__setattr__(
            self, "close_time", ensure_utc(self.close_time, field="close_time")
        )
        object.__setattr__(
            self,
            "volume",
            ensure_non_negative_decimal(self.volume, field="volume"),
        )
        require(
            isinstance(self.symbol_code, SymbolCode), "symbol_code must be a SymbolCode"
        )
        require(isinstance(self.timeframe, Timeframe), "timeframe must be a Timeframe")
        require(
            self.close_time > self.open_time,
            "close_time must be after open_time",
        )
        require(self.tick_count >= 0, "tick_count must be non-negative")
        require(
            self.high.value >= self.low.value,
            "high must be >= low",
            high=str(self.high),
            low=str(self.low),
        )
        require(
            self.high.value >= self.open.value and self.high.value >= self.close.value,
            "high must be >= open and close",
        )
        require(
            self.low.value <= self.open.value and self.low.value <= self.close.value,
            "low must be <= open and close",
        )

    @classmethod
    def create(
        cls,
        *,
        symbol_code: str | SymbolCode,
        timeframe: Timeframe | str,
        open_time: datetime,
        close_time: datetime,
        open: Price | Decimal | int | str,
        high: Price | Decimal | int | str,
        low: Price | Decimal | int | str,
        close: Price | Decimal | int | str,
        volume: Decimal | int | str = 0,
        tick_count: int = 0,
        symbol_id: UUID | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: build a validated OHLCV candle."""
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
            "open_time": open_time,
            "close_time": close_time,
            "open": ensure_price(open, field="open"),
            "high": ensure_price(high, field="high"),
            "low": ensure_price(low, field="low"),
            "close": ensure_price(close, field="close"),
            "volume": ensure_non_negative_decimal(volume, field="volume"),
            "tick_count": tick_count,
            "symbol_id": symbol_id,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "symbol_id": str(self.symbol_id) if self.symbol_id else None,
            "timeframe": self.timeframe.value,
            "open_time": self.open_time.isoformat(),
            "close_time": self.close_time.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume),
            "tick_count": self.tick_count,
        }
