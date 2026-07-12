"""Paper Market Listener — consume MT5 ticks/candles/symbols (read-only).

Never calls order_send(). Uses Mock/live MT5 market data only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.application.services.mt5_market_data import MT5MarketDataService
from app.domain.entities.mt5_market import MT5Rate, MT5SymbolInfo, MT5Tick
from app.domain.market_data.timeframe import Timeframe


@dataclass(frozen=True, slots=True)
class PaperQuote:
    """Normalized quote snapshot for the virtual broker."""

    symbol: str
    bid: Decimal
    ask: Decimal
    mid: Decimal
    timestamp: datetime
    source: str = "tick"

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "bid": str(self.bid),
            "ask": str(self.ask),
            "mid": str(self.mid),
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }


@dataclass
class PaperMarketListener:
    """Live market data consumer for paper trading (MT5 read-only)."""

    market_data: MT5MarketDataService
    _last_quote: PaperQuote | None = field(default=None, init=False)
    _last_candle: MT5Rate | None = field(default=None, init=False)
    _last_symbol: MT5SymbolInfo | None = field(default=None, init=False)

    @property
    def last_quote(self) -> PaperQuote | None:
        return self._last_quote

    def latest_tick(self, symbol: str) -> PaperQuote:
        tick: MT5Tick = self.market_data.latest_tick(symbol)
        quote = PaperQuote(
            symbol=tick.symbol,
            bid=tick.bid,
            ask=tick.ask,
            mid=tick.mid,
            timestamp=(
                tick.timestamp
                if tick.timestamp.tzinfo
                else tick.timestamp.replace(tzinfo=UTC)
            ),
            source="tick",
        )
        self._last_quote = quote
        return quote

    def latest_candle(self, symbol: str, timeframe: str = "m15") -> MT5Rate | None:
        tf = Timeframe.parse(timeframe)
        candle = self.market_data.latest_candle(symbol, tf)
        self._last_candle = candle
        if candle is not None and self._last_quote is None:
            self._last_quote = PaperQuote(
                symbol=symbol.strip().upper(),
                bid=candle.close,
                ask=candle.close,
                mid=candle.close,
                timestamp=datetime.now(UTC),
                source="candle",
            )
        return candle

    def symbol_update(self, symbol: str) -> MT5SymbolInfo:
        info = self.market_data.symbol_info(symbol)
        self._last_symbol = info
        if info.bid is not None and info.ask is not None:
            self._last_quote = PaperQuote(
                symbol=info.code,
                bid=info.bid,
                ask=info.ask,
                mid=(info.bid + info.ask) / Decimal("2"),
                timestamp=datetime.now(UTC),
                source="symbol",
            )
        return info

    def list_symbols(self) -> list[MT5SymbolInfo]:
        return self.market_data.list_symbols()
