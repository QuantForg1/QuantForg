"""Historical Replay Engine — candle/tick replay with virtual clock.

Offline only. Never connects to a live broker. Never calls order_send().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.entities.backtest import ReplayController, VirtualClock
from app.domain.enums.backtest import ReplayControlState, ReplayMode
from app.domain.market_data.candle import Candle
from app.domain.market_data.tick import Tick
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode


@dataclass(frozen=True, slots=True)
class ReplayBar:
    """Normalized bar used by the replay engine (candle or tick-as-bar)."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")
    index: int = 0

    @property
    def mid(self) -> Decimal:
        return self.close


@dataclass
class HistoricalReplayEngine:
    """Deterministic historical replay with pause / resume / step / speed."""

    mode: ReplayMode = ReplayMode.CANDLE
    controller: ReplayController = field(default_factory=ReplayController)
    _bars: list[ReplayBar] = field(default_factory=list, init=False)
    _ticks: list[Tick] = field(default_factory=list, init=False)

    @property
    def bars(self) -> tuple[ReplayBar, ...]:
        return tuple(self._bars)

    @property
    def clock(self) -> VirtualClock | None:
        return self.controller.clock

    def load_candles(self, candles: list[Candle]) -> None:
        """Load OHLCV candles for candle-mode replay."""
        self.mode = ReplayMode.CANDLE
        self.controller.mode = ReplayMode.CANDLE
        ordered = sorted(candles, key=lambda c: c.open_time)
        self._bars = [
            ReplayBar(
                timestamp=c.close_time,
                open=c.open.value,
                high=c.high.value,
                low=c.low.value,
                close=c.close.value,
                volume=c.volume,
                index=i,
            )
            for i, c in enumerate(ordered)
        ]
        self._ticks = []

    def load_ticks(self, ticks: list[Tick]) -> None:
        """Load ticks for tick-mode replay (each tick becomes a synthetic bar)."""
        self.mode = ReplayMode.TICK
        self.controller.mode = ReplayMode.TICK
        ordered = sorted(ticks, key=lambda t: t.timestamp)
        self._ticks = list(ordered)
        self._bars = [
            ReplayBar(
                timestamp=t.timestamp,
                open=t.price.value,
                high=t.price.value,
                low=t.price.value,
                close=t.price.value,
                volume=t.volume or Decimal("0"),
                index=i,
            )
            for i, t in enumerate(ordered)
        ]

    def load_raw_bars(
        self,
        rows: list[dict[str, object]],
        *,
        mode: ReplayMode = ReplayMode.CANDLE,
    ) -> None:
        """Load bars from plain dicts (API / tests) without MT5."""
        self.mode = mode
        self.controller.mode = mode
        bars: list[ReplayBar] = []
        for i, row in enumerate(rows):
            ts_raw = (
                row.get("timestamp") or row.get("close_time") or row.get("open_time")
            )
            if isinstance(ts_raw, datetime):
                ts = ts_raw if ts_raw.tzinfo else ts_raw.replace(tzinfo=UTC)
            else:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
            o = Decimal(str(row["open"]))
            h = Decimal(str(row.get("high", o)))
            low = Decimal(str(row.get("low", o)))
            c = Decimal(str(row["close"]))
            vol = Decimal(str(row.get("volume", "0")))
            bars.append(
                ReplayBar(
                    timestamp=ts,
                    open=o,
                    high=h,
                    low=low,
                    close=c,
                    volume=vol,
                    index=i,
                )
            )
        bars.sort(key=lambda b: b.timestamp)
        self._bars = [
            ReplayBar(
                timestamp=b.timestamp,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                index=i,
            )
            for i, b in enumerate(bars)
        ]

    def start(self) -> None:
        if not self._bars:
            self.controller.start(total=0, start_at=datetime.now(UTC))
            return
        self.controller.start(total=len(self._bars), start_at=self._bars[0].timestamp)

    def pause(self) -> None:
        self.controller.pause()

    def resume(self) -> None:
        self.controller.resume()

    def set_speed(self, speed: float) -> None:
        self.controller.set_speed(speed)

    def step_forward(self) -> ReplayBar | None:
        """Advance one bar/tick; updates virtual clock. Returns bar or None."""
        if self.controller.state is ReplayControlState.PAUSED:
            return None
        idx = self.controller.step_forward()
        if idx is None:
            return None
        bar = self._bars[idx]
        if self.controller.clock is not None:
            # Force advance even if pause was toggled mid-step incorrectly
            self.controller.clock._paused = False
            self.controller.clock.advance_to(bar.timestamp)
        return bar

    def run_all(self) -> list[ReplayBar]:
        """Replay every remaining bar (respects pause — call resume first)."""
        out: list[ReplayBar] = []
        while True:
            bar = self.step_forward()
            if bar is None:
                break
            out.append(bar)
        return out

    def remaining(self) -> int:
        return max(0, self.controller.total - self.controller.index)

    @staticmethod
    def candles_from_raw(
        *,
        symbol: str,
        timeframe: str,
        rows: list[dict[str, object]],
    ) -> list[Candle]:
        """Helper: build domain Candles from raw OHLC dicts."""
        tf = Timeframe.parse(timeframe)
        code = SymbolCode(value=symbol.strip().upper())
        candles: list[Candle] = []
        for row in rows:
            open_raw = row.get("open_time") or row.get("timestamp")
            close_raw = row.get("close_time") or open_raw
            assert open_raw is not None and close_raw is not None
            open_time = (
                open_raw
                if isinstance(open_raw, datetime)
                else datetime.fromisoformat(str(open_raw).replace("Z", "+00:00"))
            )
            close_time = (
                close_raw
                if isinstance(close_raw, datetime)
                else datetime.fromisoformat(str(close_raw).replace("Z", "+00:00"))
            )
            if open_time.tzinfo is None:
                open_time = open_time.replace(tzinfo=UTC)
            if close_time.tzinfo is None:
                close_time = close_time.replace(tzinfo=UTC)
            if close_time <= open_time:
                close_time = open_time + tf.duration
            candles.append(
                Candle.create(
                    symbol_code=code,
                    timeframe=tf,
                    open_time=open_time,
                    close_time=close_time,
                    open=str(row["open"]),
                    high=str(row.get("high", row["open"])),
                    low=str(row.get("low", row["open"])),
                    close=str(row["close"]),
                    volume=str(row.get("volume", "0")),
                )
            )
        return candles
