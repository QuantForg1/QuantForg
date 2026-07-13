"""Bridge legacy generic JSON feeds into provider interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.intelligence.providers import (
    CalendarEvent,
    NewsArticle,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
)
from app.infrastructure.intelligence.runtime import ProviderRuntime
from app.infrastructure.news.configured_feed import (
    ConfiguredHttpEconomicCalendar,
    ConfiguredHttpNewsFeed,
)


@dataclass
class GenericJsonNewsProvider:
    url: str
    priority: int = 80
    name: str = "generic_json_news"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def configured(self) -> bool:
        return bool(self.url.strip())

    def health(self) -> ProviderHealth:
        configured = self.configured()
        status = (
            ProviderHealthStatus.HEALTHY
            if configured
            else ProviderHealthStatus.UNCONFIGURED
        )
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.NEWS,
            configured=configured,
            priority=self.priority,
            status=status,
        )

    def list_news(self, *, limit: int = 20) -> list[NewsArticle]:
        if not self.configured():
            return []
        feed = ConfiguredHttpNewsFeed(url=self.url)
        raw = feed.list_news(limit=limit)
        return [
            NewsArticle(
                id=i.id,
                title=i.title,
                summary=i.summary,
                source=i.source,
                url=i.url,
                published_at=i.published_at,
                provider=self.name,
                symbols=i.symbols,
            )
            for i in raw
        ]


@dataclass
class GenericJsonCalendarProvider:
    url: str
    priority: int = 80
    name: str = "generic_json_calendar"
    runtime: ProviderRuntime = field(default_factory=ProviderRuntime)

    def configured(self) -> bool:
        return bool(self.url.strip())

    def health(self) -> ProviderHealth:
        configured = self.configured()
        status = (
            ProviderHealthStatus.HEALTHY
            if configured
            else ProviderHealthStatus.UNCONFIGURED
        )
        return self.runtime.metrics.to_health(
            name=self.name,
            kind=ProviderKind.ECONOMIC_CALENDAR,
            configured=configured,
            priority=self.priority,
            status=status,
        )

    def list_events(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> list[CalendarEvent]:
        if not self.configured():
            return []
        cal = ConfiguredHttpEconomicCalendar(url=self.url)
        raw = cal.list_events(limit=limit, as_of=as_of)
        return [
            CalendarEvent(
                id=e.id,
                title=e.title,
                country=e.country,
                impact=e.impact,
                scheduled_at=e.scheduled_at,
                provider=self.name,
                actual=e.actual,
                forecast=e.forecast,
                previous=e.previous,
            )
            for e in raw
        ]
