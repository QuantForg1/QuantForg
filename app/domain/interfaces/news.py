"""Ports for optional licensed news / economic calendar feeds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NewsItem:
    id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: str
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EconomicEvent:
    id: str
    title: str
    country: str
    impact: str
    scheduled_at: str
    actual: str = ""
    forecast: str = ""
    previous: str = ""
    source: str = ""


class NewsFeedPort(Protocol):
    """Optional configured news provider. Empty when unset."""

    def list_news(self, *, limit: int = 20) -> list[NewsItem]:
        ...


class EconomicCalendarPort(Protocol):
    """Optional configured economic calendar provider. Empty when unset."""

    def list_events(
        self,
        *,
        limit: int = 20,
        as_of: datetime | None = None,
    ) -> list[EconomicEvent]:
        ...
