"""LiquidityProfileResolver — resolve qualitative liquidity regime.

Why it exists
-------------
Given a market, session, and day type, returns a
:class:`LiquidityProfile` from :class:`LiquidityProfilePort`. Performs no
order-book or indicator maths.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.interfaces.market_context import LiquidityProfilePort
from app.domain.market_context.enums import DayType, MarketSession
from app.domain.market_context.value_objects import LiquidityProfile


@dataclass(frozen=True, slots=True)
class LiquidityProfileResolver:
    """Resolve liquidity profile metadata via the liquidity port."""

    profiles: LiquidityProfilePort

    def resolve(
        self,
        market_code: str,
        session: MarketSession,
        day_type: DayType,
    ) -> LiquidityProfile:
        """Return the configured liquidity profile for the context key."""
        return self.profiles.get_profile(market_code, session, day_type)
