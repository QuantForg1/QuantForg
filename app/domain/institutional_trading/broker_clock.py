"""MT5 trade-server clock offset.

MT5 reports tick, deal, order and position times as the *trade server's*
wall clock encoded as epoch seconds (Weltrade-Real: UTC+2 in winter). Read as
UTC they are hours ahead, so a UTC day boundary for the daily loss stop lands
in the wrong place. Verified 16 Nov 2026: position 704115432 closed at
07:47:50 UTC per Railway logs; MT5 reported 09:47:43.

The offset is learned from fresh quotes: (tick time - real UTC now) rounded to
whole hours, accepted only when the residue is under 2 minutes (a live
market). It is never assumed; until it is observed ``offset()`` is None and
callers that need exact day boundaries must fail closed.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

_MAX_RESIDUE_SECONDS = 120
_MAX_HOURS = 14
_VALID_FOR = timedelta(days=3)

_lock = threading.Lock()
_offset: timedelta | None = None
_observed_at: datetime | None = None


def observe_server_epoch(
    server_epoch: int | float, *, now: datetime | None = None
) -> None:
    """Record the offset from a fresh tick's server timestamp."""
    global _offset, _observed_at
    moment = now or datetime.now(UTC)
    try:
        diff = float(server_epoch) - moment.timestamp()
    except (TypeError, ValueError):
        return
    hours = round(diff / 3600)
    if abs(hours) > _MAX_HOURS or abs(diff - hours * 3600) > _MAX_RESIDUE_SECONDS:
        return  # stale tick (market closed) or bad clock: learn nothing
    with _lock:
        _offset = timedelta(hours=hours)
        _observed_at = moment


def offset(*, now: datetime | None = None) -> timedelta | None:
    moment = now or datetime.now(UTC)
    with _lock:
        if _offset is None or _observed_at is None:
            return None
        if moment - _observed_at > _VALID_FOR:
            return None
        return _offset


def server_epoch_to_utc(server_epoch: int | float) -> datetime:
    """Convert an MT5 server timestamp to real UTC (raw when offset unknown)."""
    ts = int(server_epoch)
    if ts > 10_000_000_000:
        ts //= 1000
    raw = datetime.fromtimestamp(ts, tz=UTC)
    off = offset()
    return raw - off if off is not None else raw


def reset_for_tests() -> None:
    global _offset, _observed_at
    with _lock:
        _offset = None
        _observed_at = None


def set_for_tests(value: timedelta | None) -> None:
    global _offset, _observed_at
    with _lock:
        _offset = value
        _observed_at = datetime.now(UTC) if value is not None else None
