"""Unit tests for market-data domain models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.exceptions.base import ValidationError
from app.domain.market_data.candle import Candle
from app.domain.market_data.quote import Quote
from app.domain.market_data.snapshot import MarketSnapshot, SymbolMarketView
from app.domain.market_data.tick import Tick
from app.domain.market_data.timeframe import Timeframe
from app.domain.value_objects.identity import SymbolCode


@pytest.mark.unit
class TestTimeframe:
    def test_parse_and_duration(self) -> None:
        assert Timeframe.parse("h1") is Timeframe.H1
        assert Timeframe.M5.duration == timedelta(minutes=5)

    def test_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            Timeframe.parse("M3")


@pytest.mark.unit
class TestTick:
    def test_create_normalises_utc_and_symbol(self) -> None:
        tick = Tick.create(
            symbol_code="eurusd",
            price="1.1000",
            volume="1.5",
            timestamp=datetime(2026, 1, 1, 12, 0, 0),
        )
        assert tick.symbol_code.value == "EURUSD"
        assert tick.timestamp.tzinfo == UTC
        assert tick.volume == Decimal("1.5")

    def test_rejects_float_price(self) -> None:
        with pytest.raises(ValidationError):
            Tick.create(symbol_code="EURUSD", price=1.1)  # type: ignore[arg-type]


@pytest.mark.unit
class TestQuoteAndSpread:
    def test_quote_mid_and_spread(self) -> None:
        quote = Quote.create(
            symbol_code="XAUUSD",
            bid="2300.10",
            ask="2300.40",
        )
        assert quote.mid.value == Decimal("2300.25")
        spread = quote.to_spread()
        assert spread.value == Decimal("0.30")
        assert spread.symbol_code == quote.symbol_code

    def test_ask_must_be_gte_bid(self) -> None:
        with pytest.raises(ValidationError):
            Quote.create(symbol_code="EURUSD", bid="1.2", ask="1.1")


@pytest.mark.unit
class TestCandle:
    def test_valid_ohlc(self) -> None:
        start = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
        candle = Candle.create(
            symbol_code="EURUSD",
            timeframe="M1",
            open_time=start,
            close_time=start + timedelta(minutes=1),
            open="1.1000",
            high="1.1010",
            low="1.0990",
            close="1.1005",
            volume="10",
            tick_count=42,
        )
        assert candle.timeframe is Timeframe.M1
        assert candle.tick_count == 42

    def test_rejects_broken_ohlc(self) -> None:
        start = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
        with pytest.raises(ValidationError):
            Candle.create(
                symbol_code="EURUSD",
                timeframe=Timeframe.M1,
                open_time=start,
                close_time=start + timedelta(minutes=1),
                open="1.10",
                high="1.09",
                low="1.08",
                close="1.085",
            )


@pytest.mark.unit
class TestMarketSnapshot:
    def test_multi_symbol_snapshot(self) -> None:
        eurusd = SymbolCode.of("EURUSD")
        gbpusd = SymbolCode.of("GBPUSD")
        tick = Tick.create(symbol_code=eurusd, price="1.1")
        quote = Quote.create(symbol_code=gbpusd, bid="1.25", ask="1.26")
        snapshot = MarketSnapshot.create(
            views=(
                SymbolMarketView(symbol_code=eurusd, tick=tick),
                SymbolMarketView(symbol_code=gbpusd, quote=quote),
            )
        )
        assert snapshot.symbol_codes == ("EURUSD", "GBPUSD")
        assert snapshot.view_for("EURUSD") is not None
        assert snapshot.view_for("USDJPY") is None

    def test_rejects_duplicate_symbols(self) -> None:
        code = SymbolCode.of("EURUSD")
        with pytest.raises(ValidationError):
            MarketSnapshot.create(
                views=(
                    SymbolMarketView(symbol_code=code),
                    SymbolMarketView(symbol_code=code),
                )
            )
