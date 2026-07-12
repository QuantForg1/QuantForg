"""VolatilityProfileResolver — resolve qualitative volatility regime.

Why it exists
-------------
Given a market, session, and day type, returns a
:class:`VolatilityProfile` from :class:`VolatilityProfilePort`. Performs no
ATR/std-dev or strategy calculations.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.interfaces.market_context import VolatilityProfilePort
from app.domain.market_context.enums import DayType, MarketSession
from app.domain.market_context.value_objects import VolatilityProfile


@dataclass(frozen=True, slots=True)
class VolatilityProfileResolver:
    """Resolve volatility profile metadata via the volatility port."""

    profiles: VolatilityProfilePort

    def resolve(
        self,
        market_code: str,
        session: MarketSession,
        day_type: DayType,
    ) -> VolatilityProfile:
        """Return the configured volatility profile for the context key."""
        return self.profiles.get_profile(market_code, session, day_type)
