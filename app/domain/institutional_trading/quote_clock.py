"""Quote age on one clock.

MT5 tick and bar ``time`` values are broker-server unix seconds. The gateway
client labels those integers with ``datetime.fromtimestamp(..., tz=UTC)``.
They are not UTC instants. On the attached gold terminal the broker clock
leads real UTC by about two hours, and that lead changes with the broker's
daylight-saving rule. Do not hardcode it.

``max(0, utc_now - stamp)`` turns any stamp that is still ahead of UTC into
age 0. A quote that is stale on the broker clock by less than that lead is
then treated as fresh. This module does not do that.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# Network and clock jitter. This is not a broker offset.
SKEW_TOLERANCE_SECONDS = 2.0


def quote_age_seconds(
    quote_time: datetime,
    *,
    now: datetime,
    broker_utc_offset: timedelta | None = None,
    skew_tolerance_seconds: float = SKEW_TOLERANCE_SECONDS,
) -> float | None:
    """Return age in seconds, or None when freshness cannot be proven.

    ``broker_utc_offset`` is broker-clock minus true UTC. When it is known,
    age is ``(now + offset) - quote_time``. A fresh broker stamp then has
    age about 0, and a stamp that is thirty minutes old on that clock has
    age about 1800.

    When the offset is unknown, a stamp that leads ``now`` by more than the
    skew tolerance is not fresh. None means the caller must fail closed.
    The lead itself is not returned as the age: that would mark a fresh
    broker quote as hours old.
    """
    if quote_time.tzinfo is None:
        quote_time = quote_time.replace(tzinfo=UTC)
    else:
        quote_time = quote_time.astimezone(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    else:
        now = now.astimezone(UTC)

    reference = now if broker_utc_offset is None else now + broker_utc_offset
    age = (reference - quote_time).total_seconds()
    if age < -float(skew_tolerance_seconds):
        return None
    if age < 0.0:
        return 0.0
    return age


def resolve_quoted_age_for_firewall(
    quote_age_seconds: float | None,
    *,
    market_data_live: bool,
    quote_clock_unaligned: bool,
    has_bid_ask: bool,
) -> float | None:
    """Age passed into the new-entry firewall.

    Legacy contexts omit age on a live tick and are still treated as fresh.
    An unaligned broker clock must not be replaced with zero. Zero is fresh
    at the 3s and 120s gates, so filling it in would treat a stale quote as
    a new quote.
    """
    if quote_clock_unaligned:
        return None
    if quote_age_seconds is None and market_data_live and has_bid_ask:
        return 0.0
    return quote_age_seconds
