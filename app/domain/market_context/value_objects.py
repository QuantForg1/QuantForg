"""Immutable value objects for the Market Context Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.entities._guards import require
from app.domain.exceptions.base import ValidationError
from app.domain.market_context.enums import (
    DayType,
    LiquidityLevel,
    MarketSession,
    VolatilityLevel,
)


def resolve_zone(tz_name: str) -> ZoneInfo:
    """Resolve an IANA timezone name to :class:`ZoneInfo` (DST-aware)."""
    name = tz_name.strip()
    require(bool(name), "timezone name must not be blank")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError(
            f"Unknown IANA timezone '{tz_name}'",
            details={"timezone": tz_name},
        ) from exc


@dataclass(frozen=True, kw_only=True, slots=True)
class SessionWindow:
    """One trading session window defined in a local timezone.

    Why it exists
    -------------
    Session schedules are expressed in exchange-local wall clocks. Storing
    ``start_local`` / ``end_local`` with an IANA timezone keeps DST transitions
    correct when converting from UTC.
    """

    session: MarketSession
    timezone: str
    start_local: time
    end_local: time
    priority: int = 0

    def __post_init__(self) -> None:
        require(
            self.session not in {MarketSession.CLOSED, MarketSession.OFF_HOURS},
            "SessionWindow must describe an active session",
            session=self.session.value,
        )
        resolve_zone(self.timezone)
        if self.start_local == self.end_local:
            raise ValidationError(
                "SessionWindow start_local and end_local must differ",
                details={"session": self.session.value},
            )

    @property
    def zone(self) -> ZoneInfo:
        """DST-aware zone for this window."""
        return resolve_zone(self.timezone)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.session.value,
            "timezone": self.timezone,
            "start_local": self.start_local.isoformat(),
            "end_local": self.end_local.isoformat(),
            "priority": self.priority,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class MarketSessionSchedule:
    """Ordered collection of session windows for a market.

    Why it exists
    -------------
    A market (e.g. FX, US equities) has one or more regional sessions.
    Higher ``priority`` wins when windows overlap (e.g. London/NY overlap).
    """

    market_code: str
    windows: tuple[SessionWindow, ...] = field(default_factory=tuple)
    reference_timezone: str = "UTC"

    def __post_init__(self) -> None:
        require(bool(self.market_code.strip()), "market_code must not be blank")
        resolve_zone(self.reference_timezone)
        object.__setattr__(
            self,
            "windows",
            tuple(sorted(self.windows, key=lambda w: w.priority, reverse=True)),
        )

    @property
    def reference_zone(self) -> ZoneInfo:
        return resolve_zone(self.reference_timezone)

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_code": self.market_code,
            "reference_timezone": self.reference_timezone,
            "windows": [w.to_dict() for w in self.windows],
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class LiquidityProfile:
    """Immutable liquidity classification for a context key.

    Why it exists
    -------------
    Captures the qualitative liquidity regime associated with a session and
    day type. Values come from configuration via :class:`LiquidityProfilePort`,
    not from indicator calculations.
    """

    level: LiquidityLevel
    session: MarketSession
    day_type: DayType
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "session": self.session.value,
            "day_type": self.day_type.value,
            "label": self.label,
        }


@dataclass(frozen=True, kw_only=True, slots=True)
class VolatilityProfile:
    """Immutable volatility classification for a context key.

    Why it exists
    -------------
    Captures the qualitative volatility regime for a session/day-type pair.
    Not an ATR or std-dev computation — catalogue metadata only.
    """

    level: VolatilityLevel
    session: MarketSession
    day_type: DayType
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "session": self.session.value,
            "day_type": self.day_type.value,
            "label": self.label,
        }
