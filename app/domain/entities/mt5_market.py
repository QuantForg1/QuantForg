"""MT5 market-data value objects — ticks and rates only (no orders)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.entities._guards import require
from app.domain.market_data.timeframe import Timeframe


@dataclass(frozen=True, slots=True)
class MT5Tick:
    """Latest bid/ask tick snapshot from MT5."""

    symbol: str
    bid: Decimal
    ask: Decimal
    timestamp: datetime
    volume: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        require(len(self.symbol) > 0, "symbol is required")
        require(self.ask >= self.bid, "ask must be >= bid")

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "bid": str(self.bid),
            "ask": str(self.ask),
            "spread": str(self.spread),
            "timestamp": self.timestamp.isoformat(),
            "volume": str(self.volume),
        }


@dataclass(frozen=True, slots=True)
class MT5Rate:
    """OHLCV candlestick / rate bar from MT5."""

    symbol: str
    timeframe: Timeframe
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_volume: int = 0
    spread_points: int = 0
    real_volume: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        require(len(self.symbol) > 0, "symbol is required")
        require(self.high >= self.low, "high must be >= low")
        require(self.tick_volume >= 0, "tick_volume must be >= 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "open_time": self.open_time.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "tick_volume": self.tick_volume,
            "spread_points": self.spread_points,
            "real_volume": str(self.real_volume),
        }


@dataclass(frozen=True, slots=True)
class MT5SymbolInfo:
    """Rich symbol metadata from MT5 (Market Watch selection aware)."""

    code: str
    description: str = ""
    digits: int = 5
    point: Decimal = Decimal("0.00001")
    contract_size: Decimal = Decimal("100000")
    selected: bool = False
    trade_mode: str = "full"
    currency_base: str = ""
    currency_profit: str = ""
    bid: Decimal | None = None
    ask: Decimal | None = None
    # Live broker constraints — populated from MT5 when available
    volume_min: Decimal = Decimal("0.01")
    volume_max: Decimal = Decimal("100")
    volume_step: Decimal = Decimal("0.01")
    stops_level: int = 0
    freeze_level: int = 0
    filling_mode: int = 0
    execution_mode: str = "market"
    margin_calc_mode: str = ""
    visible: bool = True
    market_open: bool = True
    trade_allowed: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", self.code.strip().upper())
        require(len(self.code) > 0, "code is required")
        require(self.digits >= 0, "digits must be >= 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "description": self.description,
            "digits": self.digits,
            "point": str(self.point),
            "contract_size": str(self.contract_size),
            "selected": self.selected,
            "trade_mode": self.trade_mode,
            "currency_base": self.currency_base,
            "currency_profit": self.currency_profit,
            "bid": str(self.bid) if self.bid is not None else None,
            "ask": str(self.ask) if self.ask is not None else None,
            "volume_min": str(self.volume_min),
            "volume_max": str(self.volume_max),
            "volume_step": str(self.volume_step),
            "stops_level": self.stops_level,
            "freeze_level": self.freeze_level,
            "filling_mode": self.filling_mode,
            "execution_mode": self.execution_mode,
            "margin_calc_mode": self.margin_calc_mode,
            "visible": self.visible,
            "market_open": self.market_open,
            "trade_allowed": self.trade_allowed,
        }
