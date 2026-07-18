"""Provider registry — priority selection, failover, health, metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeVar

from app.domain.intelligence.event_engine import IntelligenceEventEngine
from app.domain.intelligence.providers import (
    CalendarEvent,
    EconomicCalendarProvider,
    IntelligenceEvent,
    MarketDataProvider,
    NewsArticle,
    NewsProvider,
    ProviderHealth,
    ProviderKind,
    QuoteSnapshot,
    SentimentProvider,
    SentimentSnapshot,
)

Provider = TypeVar(
    "Provider",
    MarketDataProvider,
    NewsProvider,
    EconomicCalendarProvider,
    SentimentProvider,
)


@dataclass
class IntelligenceProviderRegistry:
    market_data: list[MarketDataProvider] = field(default_factory=list)
    news: list[NewsProvider] = field(default_factory=list)
    calendars: list[EconomicCalendarProvider] = field(default_factory=list)
    sentiment: list[SentimentProvider] = field(default_factory=list)
    event_engine: IntelligenceEventEngine = field(
        default_factory=IntelligenceEventEngine
    )

    def _sorted(self, providers: list[Provider]) -> list[Provider]:
        return sorted(providers, key=lambda p: getattr(p, "priority", 100))

    def list_providers(self) -> list[ProviderHealth]:
        health: list[ProviderHealth] = []
        for market_provider in self._sorted(self.market_data):
            health.append(market_provider.health())
        for news_provider in self._sorted(self.news):
            health.append(news_provider.health())
        for calendar_provider in self._sorted(self.calendars):
            health.append(calendar_provider.health())
        for sentiment_provider in self._sorted(self.sentiment):
            health.append(sentiment_provider.health())
        return health

    def status(self) -> dict[str, object]:
        providers = self.list_providers()
        by_kind: dict[str, list[dict[str, object]]] = {
            k.value: [] for k in ProviderKind
        }
        for h in providers:
            by_kind[h.kind.value].append(
                {
                    "name": h.name,
                    "status": h.status.value,
                    "configured": h.configured,
                    "priority": h.priority,
                    "latency_ms": h.latency_ms,
                    "last_error": h.last_error,
                    "requests": h.requests,
                    "failures": h.failures,
                    "cache_hits": h.cache_hits,
                    "rate_limited": h.rate_limited,
                }
            )
        configured = sum(1 for h in providers if h.configured)
        healthy = sum(1 for h in providers if h.status.value == "healthy")
        return {
            "provider_count": len(providers),
            "configured_count": configured,
            "healthy_count": healthy,
            "kinds": by_kind,
            "failover": "priority_ascending",
            "caching": "ttl",
            "rate_limits": "token_bucket",
            "timeouts": "per_provider",
        }

    def get_quote(self, symbol: str) -> QuoteSnapshot | None:
        for provider in self._sorted(self.market_data):
            if not provider.configured():
                continue
            quote = provider.get_quote(symbol)
            if quote is not None:
                return quote
        return None

    def list_quotes(self, symbols: list[str] | None = None) -> list[QuoteSnapshot]:
        for provider in self._sorted(self.market_data):
            if not provider.configured():
                continue
            quotes = provider.list_quotes(symbols)
            if quotes:
                return quotes
        return []

    def list_news(self, *, limit: int = 20) -> list[NewsArticle]:
        merged: list[NewsArticle] = []
        seen: set[str] = set()
        for provider in self._sorted(self.news):
            if not provider.configured():
                continue
            for item in provider.list_news(limit=limit):
                key = item.title.strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
                if len(merged) >= limit:
                    return merged
        return merged

    def list_calendar(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> list[CalendarEvent]:
        merged: list[CalendarEvent] = []
        seen: set[str] = set()
        for provider in self._sorted(self.calendars):
            if not provider.configured():
                continue
            for item in provider.list_events(limit=limit, as_of=as_of):
                key = f"{item.title}|{item.scheduled_at}".lower()
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
                if len(merged) >= limit:
                    return merged
        return merged

    def get_sentiment(self, symbol: str) -> SentimentSnapshot | None:
        for provider in self._sorted(self.sentiment):
            if not provider.configured():
                continue
            snap = provider.get_sentiment(symbol)
            if snap is not None:
                return snap
        return None

    def build_events(
        self,
        *,
        limit: int = 30,
        portfolio_symbols: tuple[str, ...] = (),
    ) -> list[IntelligenceEvent]:
        news = self.list_news(limit=limit)
        calendar = self.list_calendar(limit=limit)
        events = [
            *self.event_engine.from_news(news, portfolio_symbols=portfolio_symbols),
            *self.event_engine.from_calendar(
                calendar, portfolio_symbols=portfolio_symbols
            ),
        ]
        events.sort(key=lambda e: e.risk_score, reverse=True)
        return events[:limit]
