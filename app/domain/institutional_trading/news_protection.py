"""High-impact news protection — disabled by default without a calendar feed."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.models import NewsProtectionStatus
from core.logging import get_logger

logger = get_logger(__name__)

# Last logged (blocked, reason) so each blackout / feed outage is recorded once
# when it starts and once when it clears, not on every few-second cycle.
_LAST_STATE: dict[str, tuple[bool, str]] = {}


class NewsFeedUnavailable(RuntimeError):
    """The calendar feed failed; never read as 'no events'."""


def _record(status: NewsProtectionStatus, *, as_of: datetime) -> NewsProtectionStatus:
    key = "news_protection"
    state = (status.blocked, status.reason)
    if _LAST_STATE.get(key) != state:
        _LAST_STATE[key] = state
        logger.warning(
            "news_protection_state",
            blocked=status.blocked,
            reason=status.reason,
            events=list(status.events),
            as_of=as_of.isoformat(),
        )
    return status


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
    ) -> Sequence[NewsEvent]: ...


@dataclass(frozen=True, slots=True)
class NewsProtection:
    """Block new entries around NFP/CPI/FOMC when enabled + feed present."""

    config: ITEConfig
    calendar: NewsCalendarPort | None = None
    fail_closed_without_feed: bool = False

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
            if self.fail_closed_without_feed:
                return NewsProtectionStatus(
                    enabled=True,
                    blocked=True,
                    reason=(
                        "News protection enabled but no calendar feed — "
                        "fail-closed (new entries paused until feed is wired)."
                    ),
                )
            return NewsProtectionStatus(
                enabled=True,
                blocked=False,
                reason=(
                    "News protection enabled but no calendar feed — "
                    "fail-open for availability; wire a feed to enforce blackouts."
                ),
            )

        try:
            hits = self.calendar.events_near(
                as_of=as_of,
                minutes_before=self.config.news_blackout_minutes_before,
                minutes_after=self.config.news_blackout_minutes_after,
            )
        except Exception as exc:
            detail = str(exc)[:160] or type(exc).__name__
            if self.fail_closed_without_feed:
                return _record(
                    NewsProtectionStatus(
                        enabled=True,
                        blocked=True,
                        reason=(
                            "News feed unavailable - fail-closed "
                            f"(new entries paused): {detail}"
                        ),
                        events=("NEWS_FEED_UNAVAILABLE",),
                    ),
                    as_of=as_of,
                )
            return _record(
                NewsProtectionStatus(
                    enabled=True,
                    blocked=False,
                    reason=f"News feed unavailable - fail-open: {detail}",
                ),
                as_of=as_of,
            )
        high = [
            e
            for e in hits
            if e.impact.lower() == "high"
            and (
                e.code.upper()
                in {c.upper() for c in self.config.high_impact_event_codes}
                or any(
                    c.upper() in (e.title or "").upper()
                    for c in self.config.high_impact_event_codes
                )
            )
        ]
        if not high:
            return _record(
                NewsProtectionStatus(
                    enabled=True,
                    blocked=False,
                    reason="No high-impact events in blackout window.",
                ),
                as_of=as_of,
            )
        codes = tuple(sorted({e.code for e in high}))
        return _record(
            NewsProtectionStatus(
                enabled=True,
                blocked=True,
                reason=f"High-impact news blackout: {', '.join(codes)}",
                events=codes,
            ),
            as_of=as_of,
        )
