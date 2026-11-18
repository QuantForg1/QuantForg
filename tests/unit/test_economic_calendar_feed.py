"""Economic calendar feed: ForexFactory-style ``date`` rows, caching, country scope."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from app.domain.institutional_trading.ai_scalping.economic_calendar_adapter import (
    EconomicCalendarNewsAdapter,
)
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.news_protection import NewsProtection
from app.infrastructure.news import configured_feed
from app.infrastructure.news.configured_feed import ConfiguredHttpEconomicCalendar

URL = "https://calendar.example/week.json"


# Shape of nfs.faireconomy.media/ff_calendar_thisweek.json (times in US Eastern).
def _row(title: str, country: str, date: str, impact: str) -> dict[str, Any]:
    return {"title": title, "country": country, "date": date, "impact": impact}


WEEK: list[dict[str, Any]] = [
    _row("CPI m/m", "CAD", "2026-11-18T08:30:00-05:00", "High"),
    _row("BusinessNZ Services Index", "NZD", "2026-11-15T16:30:00-05:00", "Low"),
    _row("FOMC Meeting Minutes", "USD", "2026-11-18T14:00:00-05:00", "High"),
    _row("Employment Change", "AUD", "2026-11-18T19:30:00-05:00", "High"),
]


class _Response:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class _Client:
    calls = 0
    payload: Any = WEEK
    fail = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        _ = args, kwargs

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def get(self, url: str) -> _Response:
        _ = url
        type(self).calls += 1
        if type(self).fail:
            raise RuntimeError("feed down")
        return _Response(type(self).payload)


@pytest.fixture(autouse=True)
def _fake_http(monkeypatch: pytest.MonkeyPatch) -> None:
    configured_feed._CALENDAR_CACHE.clear()
    _Client.calls = 0
    _Client.payload = WEEK
    _Client.fail = False
    monkeypatch.setattr(httpx, "Client", _Client)


def _protection(countries: frozenset[str] = frozenset()) -> NewsProtection:
    cfg = ITEConfig(news_protection_enabled=True)
    feed = ConfiguredHttpEconomicCalendar(url=URL)
    return NewsProtection(
        config=cfg,
        calendar=EconomicCalendarNewsAdapter(feed=feed, countries=countries),
    )


@pytest.mark.unit
def test_date_key_is_read_as_scheduled_time() -> None:
    events = ConfiguredHttpEconomicCalendar(url=URL).list_events(limit=10)
    fomc = next(e for e in events if e.title == "FOMC Meeting Minutes")
    assert fomc.scheduled_at == "2026-11-18T14:00:00-05:00"


@pytest.mark.unit
def test_fomc_minutes_blocks_inside_window() -> None:
    # 14:00 New York = 19:00 UTC; 18:45 UTC is inside the 30 min window.
    status = _protection(frozenset({"USD"})).evaluate(
        as_of=datetime(2026, 11, 18, 18, 45, tzinfo=UTC)
    )
    assert status.blocked is True
    assert "FOMC" in status.events


@pytest.mark.unit
def test_outside_window_does_not_block() -> None:
    status = _protection(frozenset({"USD"})).evaluate(
        as_of=datetime(2026, 11, 18, 17, 0, tzinfo=UTC)
    )
    assert status.blocked is False


@pytest.mark.unit
def test_country_scope_ignores_other_currencies() -> None:
    # CAD CPI at 13:30 UTC: blocks with no scope, not when scoped to USD.
    as_of = datetime(2026, 11, 18, 13, 40, tzinfo=UTC)
    assert _protection().evaluate(as_of=as_of).blocked is True
    assert _protection(frozenset({"USD"})).evaluate(as_of=as_of).blocked is False


@pytest.mark.unit
def test_rows_nearest_as_of_survive_limit() -> None:
    rows = [
        _row(f"Filler {i}", "JPY", "2026-11-16T01:00:00Z", "Low") for i in range(200)
    ]
    rows.append(WEEK[2])
    _Client.payload = rows
    events = ConfiguredHttpEconomicCalendar(url=URL).list_events(
        limit=5, as_of=datetime(2026, 11, 18, 19, 0, tzinfo=UTC)
    )
    assert events[0].title == "FOMC Meeting Minutes"


@pytest.mark.unit
def test_feed_is_cached_and_stale_copy_kept_on_failure() -> None:
    feed = ConfiguredHttpEconomicCalendar(url=URL, cache_ttl_seconds=900)
    for _ in range(20):
        feed.list_events(limit=10)
    assert _Client.calls == 1
    expired = ConfiguredHttpEconomicCalendar(url=URL, cache_ttl_seconds=0)
    _Client.fail = True
    events = expired.list_events(limit=10)
    assert _Client.calls == 2
    assert len(events) == len(WEEK)
