"""Adapt configured HTTP economic calendar → NewsProtection calendar port."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.institutional_trading.news_protection import NewsEvent
from core.logging import get_logger

logger = get_logger(__name__)

_HIGH_CODES = (
    "NFP",
    "NONFARM",
    "FOMC",
    "INTEREST",
    "RATE",
    "CPI",
    "INFLATION",
    "GDP",
    "ECB",
    "FED",
)


def _parse_when(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def _impact_of(row_impact: str, title: str) -> str:
    impact = (row_impact or "").strip().lower()
    if impact in {"high", "medium", "low"}:
        return impact
    upper = (title or "").upper()
    if any(code in upper for code in _HIGH_CODES):
        return "high"
    if impact in {"3", "red", "critical"}:
        return "high"
    return "medium" if impact else "low"


def _code_of(title: str, event_id: str) -> str:
    upper = f"{title} {event_id}".upper()
    for code in _HIGH_CODES:
        if code in upper:
            return code
    return (event_id or title or "EVENT")[:32].upper()


@dataclass(frozen=True, slots=True)
class EconomicCalendarNewsAdapter:
    """Wraps ``ConfiguredHttpEconomicCalendar`` (or any list_events feed)."""

    feed: Any
    # Upper-case calendar country codes allowed to trigger a blackout.
    # Empty = every country (previous behaviour).
    countries: frozenset[str] = frozenset()

    def events_near(
        self,
        *,
        as_of: datetime,
        minutes_before: int,
        minutes_after: int,
    ) -> Sequence[NewsEvent]:
        try:
            rows = list(self.feed.list_events(limit=80, as_of=as_of) or [])
        except Exception:
            logger.exception("economic_calendar_adapter_fetch_failed")
            return ()
        start = as_of - timedelta(minutes=max(0, int(minutes_before)))
        end = as_of + timedelta(minutes=max(0, int(minutes_after)))
        out: list[NewsEvent] = []
        for row in rows:
            title = str(getattr(row, "title", "") or "")
            scheduled = _parse_when(str(getattr(row, "scheduled_at", "") or ""))
            if scheduled is None or not (start <= scheduled <= end):
                continue
            if self.countries:
                country = str(getattr(row, "country", "") or "").strip().upper()
                if country not in self.countries:
                    continue
            event_id = str(getattr(row, "id", "") or title)
            out.append(
                NewsEvent(
                    code=_code_of(title, event_id),
                    title=title[:300],
                    scheduled_at=scheduled,
                    impact=_impact_of(str(getattr(row, "impact", "") or ""), title),
                )
            )
        return tuple(out)


def build_configured_news_calendar() -> EconomicCalendarNewsAdapter | None:
    """Return adapter when ECONOMIC_CALENDAR_FEED_URL is set; else None."""
    try:
        from app.infrastructure.news.configured_feed import (
            ConfiguredHttpEconomicCalendar,
        )
        from core.config.settings import get_settings

        settings = get_settings()
        url = str(getattr(settings, "economic_calendar_feed_url", "") or "").strip()
        if not url:
            return None
        raw_countries = str(getattr(settings, "economic_calendar_countries", "") or "")
        countries = frozenset(
            c.strip().upper() for c in raw_countries.split(",") if c.strip()
        )
        return EconomicCalendarNewsAdapter(
            feed=ConfiguredHttpEconomicCalendar(url=url),
            countries=countries,
        )
    except Exception:
        logger.exception("build_configured_news_calendar_failed")
        return None
