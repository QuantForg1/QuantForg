"""News protection never reads a dead calendar feed as 'no events'."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.domain.institutional_trading.ai_scalping.economic_calendar_adapter import (
    EconomicCalendarNewsAdapter,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.news_protection import (
    NewsFeedUnavailable,
    NewsProtection,
)
from app.infrastructure.news import configured_feed as cf

NOW = datetime(2026, 11, 18, 18, 45, tzinfo=UTC)
CFG = replace(DEFAULT_ITE_CONFIG, news_protection_enabled=True)


class _DeadFeed:
    def list_events(self, *, limit: int = 20, as_of=None, strict: bool = False):
        raise cf.CalendarFeedUnavailable("down")


class _Row:
    def __init__(self, title: str, when: datetime) -> None:
        self.id = title
        self.title = title
        self.scheduled_at = when.isoformat()
        self.impact = "high"
        self.country = "US"


class _LiveFeed:
    def list_events(self, *, limit: int = 20, as_of=None, strict: bool = False):
        return [_Row("FOMC Meeting Minutes", NOW + timedelta(minutes=15))]


def test_adapter_raises_instead_of_returning_no_events() -> None:
    adapter = EconomicCalendarNewsAdapter(feed=_DeadFeed())
    with pytest.raises(NewsFeedUnavailable):
        adapter.events_near(as_of=NOW, minutes_before=30, minutes_after=30)


def test_dead_feed_blocks_entries_when_fail_closed() -> None:
    prot = NewsProtection(
        config=CFG,
        calendar=EconomicCalendarNewsAdapter(feed=_DeadFeed()),
        fail_closed_without_feed=True,
    )
    status = prot.evaluate(as_of=NOW)
    assert status.blocked is True
    assert "fail-closed" in status.reason
    assert status.events == ("NEWS_FEED_UNAVAILABLE",)


def test_dead_feed_is_explicit_when_fail_open() -> None:
    prot = NewsProtection(
        config=CFG,
        calendar=EconomicCalendarNewsAdapter(feed=_DeadFeed()),
        fail_closed_without_feed=False,
    )
    status = prot.evaluate(as_of=NOW)
    assert status.blocked is False
    assert "unavailable" in status.reason


def test_fomc_inside_window_blocks() -> None:
    prot = NewsProtection(
        config=CFG,
        calendar=EconomicCalendarNewsAdapter(feed=_LiveFeed()),
        fail_closed_without_feed=True,
    )
    status = prot.evaluate(as_of=NOW)
    assert status.blocked is True
    assert status.reason.startswith("High-impact news blackout: FOMC")


def test_default_scalping_config_fails_closed() -> None:
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )

    assert DEFAULT_AI_SCALPING_CONFIG.news_fail_closed_without_feed is True


def test_http_feed_strict_raises_without_good_copy(monkeypatch) -> None:
    cf._CALENDAR_CACHE.clear()

    def boom(*a, **k):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx.Client, "get", boom)
    feed = cf.ConfiguredHttpEconomicCalendar(url="https://calendar.invalid/x.json")
    assert feed.list_events(as_of=NOW) == []  # display callers unchanged
    with pytest.raises(cf.CalendarFeedUnavailable):
        feed.list_events(as_of=NOW, strict=True)


def test_http_feed_strict_uses_recent_good_copy(monkeypatch) -> None:
    import time

    url = "https://calendar.invalid/y.json"
    cf._CALENDAR_CACHE.clear()
    row = {"title": "FOMC", "scheduled_at": NOW.isoformat(), "impact": "high"}
    # Fetched 1h ago: past the 15-min TTL, inside the 24h stale allowance.
    cf._CALENDAR_CACHE[url] = (time.monotonic() - 3600, [row])

    def boom(*a, **k):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx.Client, "get", boom)
    events = cf.ConfiguredHttpEconomicCalendar(url=url).list_events(
        as_of=NOW, strict=True
    )
    assert [e.title for e in events] == ["FOMC"]
    cf._CALENDAR_CACHE[url] = (time.monotonic() - 25 * 3600, [row])
    with pytest.raises(cf.CalendarFeedUnavailable):
        cf.ConfiguredHttpEconomicCalendar(url=url).list_events(as_of=NOW, strict=True)
    cf._CALENDAR_CACHE.clear()
