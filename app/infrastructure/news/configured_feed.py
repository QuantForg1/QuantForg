"""Configured HTTP JSON feeds for news / economic calendar (operator-supplied).

Never invents headlines or events. When URLs are unset, returns empty lists.
Expected JSON shapes (arrays or ``{items:[...]}``) from licensed providers
you configure — QuantForg does not ship a vendor SDK here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from app.domain.interfaces.news import EconomicEvent, NewsItem

logger = logging.getLogger(__name__)


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("items", "data", "events", "articles", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


@dataclass(frozen=True, slots=True)
class NullNewsFeed:
    def list_news(self, *, limit: int = 20) -> list[NewsItem]:
        _ = limit
        return []


@dataclass(frozen=True, slots=True)
class NullEconomicCalendar:
    def list_events(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> list[EconomicEvent]:
        _ = limit, as_of
        return []


@dataclass(frozen=True, slots=True)
class ConfiguredHttpNewsFeed:
    """GET JSON from ``NEWS_INTELLIGENCE_FEED_URL`` when configured."""

    url: str
    timeout_seconds: float = 8.0

    def list_news(self, *, limit: int = 20) -> list[NewsItem]:
        if not self.url.strip():
            return []
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(self.url.strip())
                response.raise_for_status()
                rows = _as_list(response.json())
        except Exception as exc:
            logger.warning("news_feed_fetch_failed", extra={"error": str(exc)})
            return []

        items: list[NewsItem] = []
        for row in rows[: max(1, limit)]:
            title = str(row.get("title") or row.get("headline") or "").strip()
            if not title:
                continue
            symbols_raw = row.get("symbols") or row.get("tickers") or []
            symbols = (
                tuple(str(s) for s in symbols_raw)
                if isinstance(symbols_raw, list)
                else ()
            )
            items.append(
                NewsItem(
                    id=str(row.get("id") or title)[:120],
                    title=title[:300],
                    summary=str(row.get("summary") or row.get("description") or "")[
                        :1000
                    ],
                    source=str(row.get("source") or "configured_feed")[:120],
                    url=str(row.get("url") or row.get("link") or "")[:500],
                    published_at=str(
                        row.get("published_at") or row.get("published") or ""
                    )[:64],
                    symbols=symbols,
                )
            )
        return items


@dataclass(frozen=True, slots=True)
class ConfiguredHttpEconomicCalendar:
    """GET JSON from ``ECONOMIC_CALENDAR_FEED_URL`` when configured."""

    url: str
    timeout_seconds: float = 8.0

    def list_events(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> list[EconomicEvent]:
        _ = as_of
        if not self.url.strip():
            return []
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(self.url.strip())
                response.raise_for_status()
                rows = _as_list(response.json())
        except Exception as exc:
            logger.warning("economic_calendar_fetch_failed", extra={"error": str(exc)})
            return []

        events: list[EconomicEvent] = []
        for row in rows[: max(1, limit)]:
            title = str(
                row.get("title") or row.get("event") or row.get("name") or ""
            ).strip()
            if not title:
                continue
            events.append(
                EconomicEvent(
                    id=str(row.get("id") or title)[:120],
                    title=title[:300],
                    country=str(row.get("country") or row.get("region") or "")[:64],
                    impact=str(row.get("impact") or row.get("importance") or "unknown")[
                        :32
                    ],
                    scheduled_at=str(
                        row.get("scheduled_at")
                        or row.get("datetime")
                        or row.get("time")
                        or ""
                    )[:64],
                    actual=str(row.get("actual") or "")[:64],
                    forecast=str(row.get("forecast") or "")[:64],
                    previous=str(row.get("previous") or "")[:64],
                    source=str(row.get("source") or "configured_feed")[:120],
                )
            )
        return events
