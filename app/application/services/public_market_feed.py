"""Platform-owned public market feed (read-only).

Priority:
1. Live MT5 gateway research feed when the shared terminal is online.
2. Licensed Twelve Data OHLCV/quote when configured (reference series).

Never invents prices. Never requires a visitor's personal MT5 connection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from app.application.dto.mt5 import MT5CandleDTO, MT5TickDTO
from app.application.services.mt5_session_guard import require_platform_market_feed
from app.domain.exceptions.base import ServiceUnavailableError, ValidationError
from app.domain.trading.gold_only import resolve_trading_symbol
from app.domain.market_data.timeframe import Timeframe
from core.config.settings import get_settings
from core.logging import get_logger

logger = get_logger(__name__)

FeedStatus = Literal["live", "closed", "delayed", "unavailable"]

_TF_TO_TWELVE: dict[str, str] = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1day",
    "W1": "1week",
}


def provider_symbol_for(symbol: str) -> str:
    """Map QuantForg/broker gold spellings to Twelve Data instrument codes."""
    code = resolve_trading_symbol(symbol).upper().replace("_I", "").replace(".I", "")
    if code in {"XAUUSD", "GOLD", "XAUUSDM"}:
        return "XAU/USD"
    return code


@dataclass(frozen=True, slots=True)
class PublicCandleBundle:
    symbol: str
    timeframe: str
    status: FeedStatus
    source: str
    as_of: str
    market_open: bool | None
    candles: list[MT5CandleDTO]
    last_price: str | None
    note: str


@dataclass(frozen=True, slots=True)
class PublicTickBundle:
    symbol: str
    status: FeedStatus
    source: str
    as_of: str
    market_open: bool | None
    tick: MT5TickDTO | None
    note: str


class PublicMarketFeedService:
    """Read-only market data for authenticated and anonymous visitors."""

    def __init__(self, market_data: Any) -> None:
        self._market_data = market_data

    async def candles(
        self,
        *,
        symbol: str,
        timeframe: str = "H1",
        count: int = 400,
    ) -> PublicCandleBundle:
        symbol = resolve_trading_symbol(symbol)
        tf = Timeframe.parse(timeframe)
        if count < 1 or count > 5000:
            raise ValidationError(
                "count must be between 1 and 5000",
                details={"count": count},
            )

        mt5 = await self._try_mt5_candles(symbol=symbol, tf=tf, count=count)
        if mt5 is not None:
            return mt5

        twelve = self._try_twelve_candles(symbol=symbol, timeframe=tf.value, count=count)
        if twelve is not None:
            return twelve

        return PublicCandleBundle(
            symbol=symbol,
            timeframe=tf.value,
            status="unavailable",
            source="none",
            as_of=datetime.now(UTC).replace(microsecond=0).isoformat(),
            market_open=None,
            candles=[],
            last_price=None,
            note=(
                "Platform market feed is offline and no licensed reference "
                "provider returned candles."
            ),
        )

    async def tick(self, *, symbol: str) -> PublicTickBundle:
        symbol = resolve_trading_symbol(symbol)
        mt5 = await self._try_mt5_tick(symbol=symbol)
        if mt5 is not None:
            return mt5

        twelve = self._try_twelve_tick(symbol=symbol)
        if twelve is not None:
            return twelve

        return PublicTickBundle(
            symbol=symbol,
            status="unavailable",
            source="none",
            as_of=datetime.now(UTC).replace(microsecond=0).isoformat(),
            market_open=None,
            tick=None,
            note=(
                "Platform market feed is offline and no licensed reference "
                "quote is available."
            ),
        )

    async def _try_mt5_candles(
        self, *, symbol: str, tf: Timeframe, count: int
    ) -> PublicCandleBundle | None:
        adapter = getattr(self._market_data, "adapter", None)
        if adapter is None:
            return None
        try:
            await require_platform_market_feed(adapter)
            rates = self._market_data.historical_candles(
                symbol,
                tf,
                count=count,
            )
        except ServiceUnavailableError as exc:
            logger.info(
                "public_market_mt5_unavailable code=%s",
                getattr(exc, "code", ""),
            )
            return None
        except (OSError, RuntimeError, ValueError) as exc:
            logger.info("public_market_mt5_candles_error error=%s", type(exc).__name__)
            return None

        candles = [MT5CandleDTO.from_rate(r) for r in rates]
        if not candles:
            # Empty MT5 rates often mean session closed — fall through to
            # licensed reference history instead of returning a blank chart.
            return None

        last = candles[-1]
        return PublicCandleBundle(
            symbol=symbol,
            timeframe=tf.value,
            status="live",
            source="mt5_gateway",
            as_of=last.open_time.astimezone(UTC).replace(microsecond=0).isoformat()
            if last.open_time.tzinfo
            else last.open_time.replace(tzinfo=UTC).isoformat(),
            market_open=True,
            candles=candles,
            last_price=last.close,
            note="Platform MT5 gateway feed.",
        )

    async def _try_mt5_tick(self, *, symbol: str) -> PublicTickBundle | None:
        adapter = getattr(self._market_data, "adapter", None)
        if adapter is None:
            return None
        try:
            await require_platform_market_feed(adapter)
            tick = self._market_data.latest_tick(symbol)
        except ServiceUnavailableError:
            return None
        except (OSError, RuntimeError, ValueError):
            return None
        dto = MT5TickDTO.from_tick(tick)
        return PublicTickBundle(
            symbol=symbol,
            status="live",
            source="mt5_gateway",
            as_of=dto.timestamp.astimezone(UTC).replace(microsecond=0).isoformat()
            if dto.timestamp.tzinfo
            else dto.timestamp.replace(tzinfo=UTC).isoformat(),
            market_open=True,
            tick=dto,
            note="Platform MT5 gateway feed.",
        )

    def _try_twelve_candles(
        self, *, symbol: str, timeframe: str, count: int
    ) -> PublicCandleBundle | None:
        settings = get_settings()
        api_key = (getattr(settings, "twelvedata_api_key", "") or "").strip()
        if not api_key:
            return None
        interval = _TF_TO_TWELVE.get(timeframe.upper())
        if not interval:
            return None
        from app.infrastructure.intelligence.runtime import ProviderRuntime

        runtime = ProviderRuntime(timeout_seconds=10.0)
        provider_symbol = provider_symbol_for(symbol)
        data = runtime.get_json(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": provider_symbol,
                "interval": interval,
                "outputsize": str(min(count, 5000)),
                "apikey": api_key,
                "order": "ASC",
            },
        )
        if not isinstance(data, dict) or data.get("status") == "error":
            return None
        rows = data.get("values")
        if not isinstance(rows, list) or not rows:
            return None

        candles: list[MT5CandleDTO] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_t = str(row.get("datetime") or "").strip()
            if not raw_t:
                continue
            try:
                # Twelve Data returns naive UTC-ish timestamps.
                open_time = datetime.fromisoformat(raw_t.replace("Z", "+00:00"))
                if open_time.tzinfo is None:
                    open_time = open_time.replace(tzinfo=UTC)
            except ValueError:
                continue
            try:
                o = str(row["open"])
                h = str(row["high"])
                low = str(row["low"])
                c = str(row["close"])
            except KeyError:
                continue
            candles.append(
                MT5CandleDTO(
                    symbol=symbol,
                    timeframe=timeframe.upper(),
                    open_time=open_time,
                    open=o,
                    high=h,
                    low=low,
                    close=c,
                    tick_volume=int(float(row.get("volume") or 0)),
                    spread_points=0,
                )
            )
        if not candles:
            return None
        last = candles[-1]
        return PublicCandleBundle(
            symbol=symbol,
            timeframe=timeframe.upper(),
            status="delayed",
            source="twelvedata",
            as_of=last.open_time.astimezone(UTC).replace(microsecond=0).isoformat(),
            market_open=None,
            candles=candles,
            last_price=last.close,
            note=(
                "Reference OHLCV from licensed Twelve Data — not broker "
                "execution prices. Labelled DELAYED."
            ),
        )

    def _try_twelve_tick(self, *, symbol: str) -> PublicTickBundle | None:
        settings = get_settings()
        api_key = (getattr(settings, "twelvedata_api_key", "") or "").strip()
        if not api_key:
            return None
        from app.infrastructure.intelligence.adapters import TwelveDataMarketProvider

        provider = TwelveDataMarketProvider(api_key=api_key)
        quote = provider.get_quote(provider_symbol_for(symbol))
        if quote is None:
            return None
        try:
            as_of = datetime.fromisoformat(str(quote.as_of).replace("Z", "+00:00"))
            if as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=UTC)
        except ValueError:
            as_of = datetime.now(UTC)
        tick = MT5TickDTO(
            symbol=symbol,
            bid=str(quote.bid),
            ask=str(quote.ask or quote.bid),
            spread=str(
                max(0.0, float(quote.ask or quote.bid) - float(quote.bid))
                if _finite(quote.bid) and _finite(quote.ask or quote.bid)
                else "0"
            ),
            timestamp=as_of,
            volume="0",
        )
        return PublicTickBundle(
            symbol=symbol,
            status="delayed",
            source="twelvedata",
            as_of=as_of.replace(microsecond=0).isoformat(),
            market_open=None,
            tick=tick,
            note="Reference quote from licensed Twelve Data — labelled DELAYED.",
        )


def _finite(raw: str) -> bool:
    try:
        float(raw)
        return True
    except (TypeError, ValueError):
        return False
