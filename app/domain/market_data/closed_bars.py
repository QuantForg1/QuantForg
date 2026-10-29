"""Closed-bar selection shared by ATR and structure.

An unfinished bar is not a completed observation. Swing confirmation, zone
detection, and ATR must use the same closed series.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def bar_is_time_aligned(candle: Candle, timeframe: Timeframe) -> bool:
    """True when the bar opens on that timeframe's UTC grid."""
    opened = as_utc(candle.open_time)
    if opened.second or opened.microsecond:
        return False
    step = int(timeframe.duration.total_seconds() // 60)
    if step <= 0:
        return False
    return int(opened.timestamp() // 60) % step == 0


def closed_analysis_bars(
    candles: Sequence[Candle] | None,
    *,
    as_of: datetime | None,
    timeframe: Timeframe,
) -> list[Candle]:
    """Closed, grid-aligned bars for structure, zones, and ATR.

    A bar still open at ``as_of`` is excluded. An unfinished bar must not
    confirm a fractal: with ``right=2`` it is one of the two bars that prove
    the newest swing, and that swing can occupy a target slot that a closed
    bar would not have confirmed.

    Broker candle stamps can lead real UTC. When the newest close leads
    ``as_of`` by more than one bar, the clocks are not comparable. Only the
    newest bar is dropped. The rest are kept and are not aged against the
    other clock, which would discard every fresh quote.
    """
    series = list(candles or [])
    if not series or as_of is None:
        return series
    moment = as_utc(as_of)
    newest = max(as_utc(c.close_time) for c in series)
    if newest > moment + timeframe.duration:
        last_open = max(as_utc(c.open_time) for c in series)
        return [
            c
            for c in series
            if as_utc(c.open_time) < last_open and bar_is_time_aligned(c, timeframe)
        ]
    return [
        c
        for c in series
        if as_utc(c.close_time) <= moment and bar_is_time_aligned(c, timeframe)
    ]
