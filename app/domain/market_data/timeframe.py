"""Timeframe vocabulary for candle bars.

Why it exists
-------------
Candles are always scoped to a timeframe (M1, H1, D1, …). Centralising the
enumeration prevents free-form strings and documents the supported set.
This is catalogue metadata — not indicator or strategy logic.
"""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

from app.domain.exceptions.base import ValidationError


class Timeframe(StrEnum):
    """Supported bar timeframes.

    Values follow the conventional short codes used across market-data
    platforms. Duration helpers are provided for validation and windowing —
    they do not compute indicators.
    """

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"
    MN1 = "MN1"

    @property
    def duration(self) -> timedelta:
        """Approximate bar duration.

        ``MN1`` uses 30 days as a conventional approximation; exact calendar
        month boundaries are the responsibility of candle producers.
        """
        mapping: dict[Timeframe, timedelta] = {
            Timeframe.M1: timedelta(minutes=1),
            Timeframe.M5: timedelta(minutes=5),
            Timeframe.M15: timedelta(minutes=15),
            Timeframe.M30: timedelta(minutes=30),
            Timeframe.H1: timedelta(hours=1),
            Timeframe.H4: timedelta(hours=4),
            Timeframe.D1: timedelta(days=1),
            Timeframe.W1: timedelta(weeks=1),
            Timeframe.MN1: timedelta(days=30),
        }
        return mapping[self]

    @classmethod
    def parse(cls, raw: str) -> Timeframe:
        """Parse a timeframe code, raising :class:`ValidationError` on failure."""
        normalised = raw.strip().upper()
        try:
            return cls(normalised)
        except ValueError as exc:
            raise ValidationError(
                f"Unsupported timeframe '{raw}'",
                details={
                    "field": "timeframe",
                    "value": raw,
                    "allowed": [t.value for t in cls],
                },
            ) from exc
