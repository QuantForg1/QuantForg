"""High-impact news protection — disabled by default without a calendar feed."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.models import NewsProtectionStatus


@dataclass(frozen=True, slots=True)
class NewsEvent:
    """Minimal calendar event contract."""

    code: str
    title: str
    scheduled_at: datetime
    impact: str = "high"  # high | medium | low


class NewsCalendarPort(Protocol):
    """Optional calendar feed. When absent, protection stays inactive."""

    def events_near(
        self,
        *,
        as_of: datetime,
        minutes_before: int,
        minutes_after: int,
    ) -> Sequence[NewsEvent]:
        ...


@dataclass(frozen=True, slots=True)
class NewsProtection:
    """Block new entries around NFP/CPI/FOMC when enabled + feed present."""

    config: ITEConfig
    calendar: NewsCalendarPort | None = None

    def evaluate(self, *, as_of: datetime) -> NewsProtectionStatus:
        if not self.config.news_protection_enabled:
            return NewsProtectionStatus(
                enabled=False,
                blocked=False,
                reason=(
                    "News protection disabled (no reliable calendar feed required)."
                ),
            )
        if self.calendar is None:
            return NewsProtectionStatus(
                enabled=True,
                blocked=False,
                reason=(
                    "News protection enabled but no calendar feed — "
                    "fail-open for availability; wire a feed to enforce blackouts."
                ),
            )

        hits = self.calendar.events_near(
            as_of=as_of,
            minutes_before=self.config.news_blackout_minutes_before,
            minutes_after=self.config.news_blackout_minutes_after,
        )
        high = [
            e
            for e in hits
            if e.impact.lower() == "high"
            and (
                e.code.upper() in {c.upper() for c in self.config.high_impact_event_codes}
                or any(
                    c.upper() in (e.title or "").upper()
                    for c in self.config.high_impact_event_codes
                )
            )
        ]
        if not high:
            return NewsProtectionStatus(
                enabled=True,
                blocked=False,
                reason="No high-impact events in blackout window.",
            )
        codes = tuple(sorted({e.code for e in high}))
        return NewsProtectionStatus(
            enabled=True,
            blocked=True,
            reason=f"High-impact news blackout: {', '.join(codes)}",
            events=codes,
        )
