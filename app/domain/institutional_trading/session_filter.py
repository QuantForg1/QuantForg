"""Session filter — London / New York / overlap only by default.

Uses a deterministic UTC-hour classifier for ITE (reproducible, no tzdata
dependency). Optional MarketContextEngine can override when available.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.models import SessionFilterResult
from app.domain.market_context.engine import MarketContextEngine
from app.domain.market_context.enums import MarketSession


def classify_session_utc(as_of: datetime) -> MarketSession:
    """Approximate FX session from UTC clock (deterministic).

    Windows (UTC hours, inclusive start / exclusive end):
    - London/NY overlap: 13:00-17:00
    - London: 07:00-16:00 (when not overlap)
    - New York: 12:00-21:00 (when not overlap)
    - Tokyo: 00:00-09:00
    - else off-hours
    """
    moment = as_of
    if moment.tzinfo is None:
        from datetime import UTC

        moment = moment.replace(tzinfo=UTC)
    else:
        from datetime import UTC

        moment = moment.astimezone(UTC)

    # Weekends → off hours
    if moment.weekday() >= 5:
        return MarketSession.OFF_HOURS

    h = moment.hour + moment.minute / 60.0
    if 13.0 <= h < 17.0:
        return MarketSession.LONDON_NY_OVERLAP
    if 7.0 <= h < 16.0:
        return MarketSession.LONDON
    if 12.0 <= h < 21.0:
        return MarketSession.NEW_YORK
    if 0.0 <= h < 9.0:
        return MarketSession.TOKYO
    return MarketSession.OFF_HOURS


@dataclass(frozen=True, slots=True)
class SessionFilter:
    """Gate entries to approved high-liquidity sessions."""

    config: ITEConfig
    context_engine: MarketContextEngine | None = None
    prefer_utc_classifier: bool = True

    def evaluate(
        self,
        *,
        as_of: datetime,
        market_code: str = "FX",
        session: MarketSession | None = None,
    ) -> SessionFilterResult:
        active = session
        if active is None and not self.prefer_utc_classifier and self.context_engine:
            try:
                ctx = self.context_engine.build(
                    market_code,
                    at=as_of,
                    symbol_code=self.config.symbol,
                )
                active = ctx.session
            except Exception:
                active = classify_session_utc(as_of)
        if active is None:
            active = classify_session_utc(as_of)

        allowed = active in self.config.allowed_sessions
        if allowed:
            reason = f"Session {active.value} is approved for trading."
        else:
            reason = (
                f"Session {active.value} is low-liquidity / outside "
                f"London-New York window — avoid new entries."
            )
        return SessionFilterResult(session=active, allowed=allowed, reason=reason)
