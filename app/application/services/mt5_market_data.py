"""MT5 market-data application service — historical candles, latest candle/tick.

No order execution, positions, or streaming subscriptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.entities.mt5_market import MT5Rate, MT5SymbolInfo, MT5Tick
from app.domain.events.mt5 import CandleReceived, MarketDataUpdated, TickReceived
from app.domain.market_data.candle import Candle
from app.domain.market_data.tick import Tick
from app.domain.market_data.timeframe import Timeframe
from app.infrastructure.brokers.mt5.adapter import MT5Adapter


@dataclass
class MT5MarketDataService:
    """Read-only market data facade over the MT5 adapter."""

    adapter: MT5Adapter
    _last_events: list[object] = field(default_factory=list, init=False)

    @property
    def last_events(self) -> tuple[object, ...]:
        return tuple(self._last_events)

    def clear_events(self) -> None:
        self._last_events.clear()

    def list_symbols(self) -> list[MT5SymbolInfo]:
        return self.adapter.list_symbols()

    def symbol_info(self, symbol: str) -> MT5SymbolInfo:
        info = self.adapter.symbol_info(symbol)
        self._emit(
            MarketDataUpdated(symbol=info.code, kind="symbol", detail="symbol_info")
        )
        return info

    def symbol_select(self, symbol: str, *, enable: bool = True) -> bool:
        ok = self.adapter.symbol_select(symbol, enable=enable)
        if ok:
            self._emit(
                MarketDataUpdated(
                    symbol=symbol.strip().upper(),
                    kind="symbol",
                    detail="selected" if enable else "deselected",
                )
            )
        return ok

    def latest_tick(self, symbol: str) -> MT5Tick:
        tick = self.adapter.latest_tick(symbol)
        domain_tick = Tick.create(
            symbol_code=tick.symbol,
            price=tick.mid,
            timestamp=tick.timestamp,
            volume=tick.volume,
        )
        self._emit(TickReceived(tick=domain_tick))
        self._emit(
            MarketDataUpdated(
                symbol=tick.symbol,
                kind="tick",
                detail=f"bid={tick.bid} ask={tick.ask}",
            )
        )
        return tick

    def historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        count: int = 100,
        start_pos: int | None = None,
    ) -> list[MT5Rate]:
        """Fetch historical rates via from / range / from_pos strategies."""
        code = symbol.strip().upper()
        if start_pos is not None:
            rates = self.adapter.copy_rates_from_pos(code, timeframe, start_pos, count)
        elif date_from is not None and date_to is not None:
            rates = self.adapter.copy_rates_range(code, timeframe, date_from, date_to)
        else:
            start = date_from or (
                datetime.now(UTC) - timeframe.duration * max(count, 1)
            )
            rates = self.adapter.copy_rates_from(code, timeframe, start, count)

        if rates:
            candle = self._to_domain_candle(rates[-1])
            self._emit(CandleReceived(candle=candle, source="mt5"))
            self._emit(
                MarketDataUpdated(
                    symbol=code,
                    kind="candle",
                    timeframe=timeframe.value,
                    detail=f"count={len(rates)}",
                )
            )
        return rates

    def latest_candle(self, symbol: str, timeframe: Timeframe) -> MT5Rate | None:
        rates = self.adapter.copy_rates_from_pos(symbol, timeframe, 0, 1)
        if not rates:
            return None
        candle = self._to_domain_candle(rates[0])
        self._emit(CandleReceived(candle=candle, source="mt5"))
        self._emit(
            MarketDataUpdated(
                symbol=symbol.strip().upper(),
                kind="candle",
                timeframe=timeframe.value,
                detail="latest",
            )
        )
        return rates[0]

    def _to_domain_candle(self, rate: MT5Rate) -> Candle:
        close_time = rate.open_time + rate.timeframe.duration
        return Candle.create(
            symbol_code=rate.symbol,
            timeframe=rate.timeframe,
            open_time=rate.open_time,
            close_time=close_time,
            open=rate.open,
            high=rate.high,
            low=rate.low,
            close=rate.close,
            volume=rate.real_volume,
            tick_count=rate.tick_volume,
        )

    def _emit(self, event: object) -> None:
        self._last_events.append(event)
        if len(self._last_events) > 50:
            self._last_events = self._last_events[-50:]
