"""News Intelligence — aggregates configured licensed feeds only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.interfaces.news import EconomicCalendarPort, EconomicEvent, NewsFeedPort, NewsItem


@dataclass(frozen=True, slots=True)
class NewsIntelligenceService:
    news_feed: NewsFeedPort
    calendar: EconomicCalendarPort

    def news(self, *, limit: int = 20) -> list[NewsItem]:
        return self.news_feed.list_news(limit=limit)

    def economic_events(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> list[EconomicEvent]:
        return self.calendar.list_events(limit=limit, as_of=as_of)

    def provider_status(self) -> dict[str, object]:
        news = self.news(limit=1)
        events = self.economic_events(limit=1)
        feed_name = type(self.news_feed).__name__
        cal_name = type(self.calendar).__name__
        return {
            "news_configured": feed_name != "NullNewsFeed",
            "calendar_configured": cal_name != "NullEconomicCalendar",
            "news_sample_count": len(news),
            "calendar_sample_count": len(events),
            "provider_layer": "registry",
        }
