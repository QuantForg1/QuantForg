"""Unit tests for provider registry and event engine."""

from __future__ import annotations

from app.application.services.provider_registry import IntelligenceProviderRegistry
from app.domain.intelligence.event_engine import IntelligenceEventEngine
from app.domain.intelligence.providers import (
    CalendarEvent,
    NewsArticle,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    QuoteSnapshot,
)


class _FakeNews:
    name = "fake_news"
    priority = 1

    def configured(self) -> bool:
        return True

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            name=self.name,
            kind=ProviderKind.NEWS,
            status=ProviderHealthStatus.HEALTHY,
            configured=True,
            priority=self.priority,
        )

    def list_news(self, *, limit: int = 20):
        return [
            NewsArticle(
                id="1",
                title="ECB rate decision lifts EURUSD",
                summary="Euro jumps after ECB decision",
                source="test",
                url="",
                published_at="2026-07-13T12:00:00Z",
                provider=self.name,
                symbols=("EURUSD",),
            )
        ][:limit]


class _EmptyNews:
    name = "empty"
    priority = 2

    def configured(self) -> bool:
        return False

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            name=self.name,
            kind=ProviderKind.NEWS,
            status=ProviderHealthStatus.UNCONFIGURED,
            configured=False,
            priority=self.priority,
        )

    def list_news(self, *, limit: int = 20):
        return []


class _FakeMarket:
    name = "fake_md"
    priority = 1

    def configured(self) -> bool:
        return True

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            name=self.name,
            kind=ProviderKind.MARKET_DATA,
            status=ProviderHealthStatus.HEALTHY,
            configured=True,
            priority=1,
        )

    def get_quote(self, symbol: str):
        return QuoteSnapshot(
            symbol=symbol,
            bid="1.1",
            ask="1.2",
            provider=self.name,
        )

    def list_quotes(self, symbols=None):
        return [self.get_quote("EURUSD")]


def test_event_engine_classifies_real_article_only() -> None:
    engine = IntelligenceEventEngine()
    events = engine.from_news(
        [
            NewsArticle(
                id="n1",
                title="Federal Reserve CPI print shocks USD",
                summary="US dollar jumps after hotter CPI",
                source="wire",
                url="https://example.com",
                published_at="2026-07-13T10:00:00Z",
                provider="finnhub",
            )
        ],
        portfolio_symbols=("EURUSD",),
    )
    assert len(events) == 1
    assert events[0].severity in {"high", "medium", "low"}
    assert "USD" in events[0].affected_currencies
    assert events[0].deterministic_summary
    assert events[0].provider == "finnhub"


def test_registry_failover_skips_unconfigured() -> None:
    registry = IntelligenceProviderRegistry(
        news=[_EmptyNews(), _FakeNews()],
        market_data=[_FakeMarket()],
    )
    news = registry.list_news(limit=5)
    assert len(news) == 1
    assert news[0].provider == "fake_news"
    status = registry.status()
    assert status["provider_count"] >= 2
    providers = registry.list_providers()
    assert any(p.status == ProviderHealthStatus.UNCONFIGURED for p in providers)


def test_event_engine_calendar_without_invention() -> None:
    engine = IntelligenceEventEngine()
    events = engine.from_calendar(
        [
            CalendarEvent(
                id="c1",
                title="Nonfarm Payrolls",
                country="US",
                impact="high",
                scheduled_at="2026-07-13T12:30:00Z",
                provider="finnhub",
                currency="USD",
            )
        ]
    )
    assert events[0].classification
    assert events[0].risk_score >= 0
    # Empty input yields empty output — never invents.
    assert engine.from_news([]) == []
    assert engine.from_calendar([]) == []
