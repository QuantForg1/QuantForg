"""Intelligence provider contracts and shared DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class ProviderKind(StrEnum):
    MARKET_DATA = "market_data"
    NEWS = "news"
    ECONOMIC_CALENDAR = "economic_calendar"
    SENTIMENT = "sentiment"


class ProviderHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"
    UNCONFIGURED = "unconfigured"


@dataclass(frozen=True, slots=True)
class QuoteSnapshot:
    symbol: str
    bid: str
    ask: str
    provider: str
    as_of: str = ""
    mid: str = ""
    source_detail: str = ""


@dataclass(frozen=True, slots=True)
class NewsArticle:
    id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: str
    provider: str
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    id: str
    title: str
    country: str
    impact: str
    scheduled_at: str
    provider: str
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    currency: str = ""


@dataclass(frozen=True, slots=True)
class SentimentSnapshot:
    symbol: str
    score: float | None
    label: str
    provider: str
    as_of: str = ""
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    name: str
    kind: ProviderKind
    status: ProviderHealthStatus
    configured: bool
    priority: int
    latency_ms: float | None = None
    last_error: str = ""
    last_success_at: str = ""
    requests: int = 0
    failures: int = 0
    cache_hits: int = 0
    rate_limited: int = 0


@dataclass(frozen=True, slots=True)
class IntelligenceEvent:
    """Normalized intelligence event derived from real provider payloads only."""

    id: str
    title: str
    summary: str
    classification: str
    severity: str
    affected_currencies: tuple[str, ...]
    affected_assets: tuple[str, ...]
    affected_sectors: tuple[str, ...]
    expected_volatility: str
    portfolio_impact: str
    risk_score: float
    provider: str
    source_url: str = ""
    published_at: str = ""
    deterministic_summary: str = ""


class MarketDataProvider(Protocol):
    name: str
    priority: int

    def configured(self) -> bool: ...

    def health(self) -> ProviderHealth: ...

    def get_quote(self, symbol: str) -> QuoteSnapshot | None: ...

    def list_quotes(self, symbols: list[str] | None = None) -> list[QuoteSnapshot]: ...


class NewsProvider(Protocol):
    name: str
    priority: int

    def configured(self) -> bool: ...

    def health(self) -> ProviderHealth: ...

    def list_news(self, *, limit: int = 20) -> list[NewsArticle]: ...


class EconomicCalendarProvider(Protocol):
    name: str
    priority: int

    def configured(self) -> bool: ...

    def health(self) -> ProviderHealth: ...

    def list_events(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> list[CalendarEvent]: ...


class SentimentProvider(Protocol):
    name: str
    priority: int

    def configured(self) -> bool: ...

    def health(self) -> ProviderHealth: ...

    def get_sentiment(self, symbol: str) -> SentimentSnapshot | None: ...


@dataclass
class ProviderMetrics:
    requests: int = 0
    failures: int = 0
    cache_hits: int = 0
    rate_limited: int = 0
    last_error: str = ""
    last_success_at: str = ""
    last_latency_ms: float | None = None

    def to_health(
        self,
        *,
        name: str,
        kind: ProviderKind,
        configured: bool,
        priority: int,
        status: ProviderHealthStatus,
    ) -> ProviderHealth:
        return ProviderHealth(
            name=name,
            kind=kind,
            status=status if configured else ProviderHealthStatus.UNCONFIGURED,
            configured=configured,
            priority=priority,
            latency_ms=self.last_latency_ms,
            last_error=self.last_error,
            last_success_at=self.last_success_at,
            requests=self.requests,
            failures=self.failures,
            cache_hits=self.cache_hits,
            rate_limited=self.rate_limited,
        )
