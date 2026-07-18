"""Build the configured intelligence provider registry."""

from __future__ import annotations

from app.application.services.provider_registry import IntelligenceProviderRegistry
from app.domain.intelligence.event_engine import IntelligenceEventEngine
from app.domain.intelligence.providers import (
    EconomicCalendarProvider,
    MarketDataProvider,
    NewsProvider,
    SentimentProvider,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.intelligence.adapters import (
    AlphaVantageMarketProvider,
    AlphaVantageSentimentProvider,
    BinanceMarketDataProvider,
    FinnhubCalendarProvider,
    FinnhubNewsProvider,
    FinnhubSentimentProvider,
    Mt5MarketDataProvider,
    PolygonMarketProvider,
    PolygonNewsProvider,
    TradingEconomicsCalendarProvider,
    TwelveDataMarketProvider,
)
from app.infrastructure.intelligence.generic_feeds import (
    GenericJsonCalendarProvider,
    GenericJsonNewsProvider,
)
from core.config.settings import Settings


def build_provider_registry(
    settings: Settings,
    *,
    mt5_adapter: MT5Adapter | None = None,
) -> IntelligenceProviderRegistry:
    market_data: list[MarketDataProvider] = []
    news: list[NewsProvider] = []
    calendars: list[EconomicCalendarProvider] = []
    sentiment: list[SentimentProvider] = []

    if mt5_adapter is not None:
        market_data.append(Mt5MarketDataProvider(adapter=mt5_adapter, priority=10))

    market_data.append(
        TwelveDataMarketProvider(
            api_key=getattr(settings, "twelvedata_api_key", "") or "",
            priority=30,
        )
    )
    market_data.append(
        PolygonMarketProvider(
            api_key=getattr(settings, "polygon_api_key", "") or "",
            priority=35,
        )
    )
    market_data.append(
        BinanceMarketDataProvider(
            enabled=bool(getattr(settings, "binance_market_data_enabled", True)),
            priority=40,
        )
    )
    market_data.append(
        AlphaVantageMarketProvider(
            api_key=getattr(settings, "alphavantage_api_key", "") or "",
            priority=50,
        )
    )

    finnhub = getattr(settings, "finnhub_api_key", "") or ""
    news.append(FinnhubNewsProvider(api_key=finnhub, priority=20))
    calendars.append(FinnhubCalendarProvider(api_key=finnhub, priority=20))
    sentiment.append(FinnhubSentimentProvider(api_key=finnhub, priority=20))

    news.append(
        PolygonNewsProvider(
            api_key=getattr(settings, "polygon_api_key", "") or "",
            priority=35,
        )
    )
    calendars.append(
        TradingEconomicsCalendarProvider(
            api_key=getattr(settings, "trading_economics_api_key", "") or "",
            priority=15,
        )
    )
    sentiment.append(
        AlphaVantageSentimentProvider(
            api_key=getattr(settings, "alphavantage_api_key", "") or "",
            priority=50,
        )
    )

    # Preserve legacy generic JSON feed env vars as lowest-priority providers.
    news_url = getattr(settings, "news_intelligence_feed_url", "") or ""
    cal_url = getattr(settings, "economic_calendar_feed_url", "") or ""
    if news_url.strip():
        news.append(GenericJsonNewsProvider(url=news_url, priority=80))
    if cal_url.strip():
        calendars.append(GenericJsonCalendarProvider(url=cal_url, priority=80))

    return IntelligenceProviderRegistry(
        market_data=market_data,
        news=news,
        calendars=calendars,
        sentiment=sentiment,
        event_engine=IntelligenceEventEngine(),
    )
