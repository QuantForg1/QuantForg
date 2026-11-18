"""Configured HTTP JSON feeds for news / economic calendar (operator-supplied).

Never invents headlines or events. When URLs are unset, returns empty lists.
Expected JSON shapes (arrays or ``{items:[...]}``) from licensed providers
you configure — QuantForg does not ship a vendor SDK here.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.domain.interfaces.news import EconomicEvent, NewsItem

logger = logging.getLogger(__name__)

# Calendar feeds change a few times a day and public providers rate-limit
# aggressive polling. The trading cycle runs every few seconds, so rows are
# cached per URL and the last good copy is kept when a refresh fails.
_CALENDAR_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
# A last good copy older than this no longer counts as a working feed.
CALENDAR_MAX_STALE_SECONDS = 24 * 3600.0


class CalendarFeedUnavailable(RuntimeError):
    """The calendar could not be fetched and no recent good copy exists."""


_CALENDAR_CACHE_LOCK = threading.Lock()
_TIME_KEYS = ("scheduled_at", "datetime", "time", "date")


def _row_when(row: dict[str, Any]) -> str:
    for key in _TIME_KEYS:
        value = row.get(key)
        if value:
            return str(value)
    return ""


def _parse_when(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _cached_calendar_rows(
    url: str, *, timeout_seconds: float, ttl_seconds: float, strict: bool = False
) -> list[dict[str, Any]]:
    now = time.monotonic()
    with _CALENDAR_CACHE_LOCK:
        hit = _CALENDAR_CACHE.get(url)
    if hit is not None and now - hit[0] < ttl_seconds:
        return hit[1]
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(url)
            response.raise_for_status()
            rows = _as_list(response.json())
    except Exception as exc:
        logger.warning(
            "economic_calendar_fetch_failed",
            extra={"error": str(exc), "stale_rows": len(hit[1]) if hit else 0},
        )
        if hit is not None and now - hit[0] < CALENDAR_MAX_STALE_SECONDS:
            return hit[1]
        if strict:
            raise CalendarFeedUnavailable(
                "economic calendar unavailable and no good copy within "
                f"{int(CALENDAR_MAX_STALE_SECONDS // 3600)}h"
            ) from exc
        return hit[1] if hit is not None else []
    with _CALENDAR_CACHE_LOCK:
        _CALENDAR_CACHE[url] = (now, rows)
    return rows


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
    cache_ttl_seconds: float = 900.0

    def list_events(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
        strict: bool = False,
    ) -> list[EconomicEvent]:
        """``strict`` raises :class:`CalendarFeedUnavailable` instead of
        returning an empty list when the feed is down (trading gate)."""
        if not self.url.strip():
            if strict:
                raise CalendarFeedUnavailable("economic calendar URL not set")
            return []
        rows = _cached_calendar_rows(
            self.url.strip(),
            timeout_seconds=self.timeout_seconds,
            ttl_seconds=self.cache_ttl_seconds,
            strict=strict,
        )
        if as_of is not None:
            # A weekly feed holds 100+ rows; keep the ones nearest ``as_of`` so
            # ``limit`` never drops the event that matters now.
            anchor = as_of if as_of.tzinfo else as_of.replace(tzinfo=UTC)

            def _distance(row: dict[str, Any]) -> float:
                when = _parse_when(_row_when(row))
                if when is None:
                    return float("inf")
                return abs((when - anchor).total_seconds())

            rows = sorted(rows, key=_distance)

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
                    scheduled_at=_row_when(row)[:64],
                    actual=str(row.get("actual") or "")[:64],
                    forecast=str(row.get("forecast") or "")[:64],
                    previous=str(row.get("previous") or "")[:64],
                    source=str(row.get("source") or "configured_feed")[:120],
                )
            )
        return events
