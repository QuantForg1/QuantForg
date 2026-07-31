"""Session filter — 24/7 named sessions with soft quality/risk weighting.

Uses a deterministic UTC-hour classifier for ITE (reproducible, no tzdata
dependency). Optional MarketContextEngine can override when available.

Hard blocks apply only to weekend / off-hours / closed market windows.
Sydney, Tokyo, London, New York, and Overlap are tradable when configured;
session quality influences scoring and risk weight, not an absolute reject.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.models import SessionFilterResult
from app.domain.institutional_trading.session_policy import (
    quality_score_for_stars,
    risk_multiplier_for_stars,
    stars_for_session,
)
from app.domain.market_context.engine import MarketContextEngine
from app.domain.market_context.enums import MarketSession


def classify_session_utc(as_of: datetime) -> MarketSession:
    """Approximate FX session from UTC clock (deterministic).

    Windows (UTC hours, inclusive start / exclusive end):
    - London/NY overlap: 13:00-17:00
    - London: 07:00-16:00 (when not overlap)
    - New York: 12:00-21:00 (when not overlap)
    - Tokyo: 00:00-09:00
    - Sydney: 21:00-06:00 (when not Tokyo)
    - else off-hours
    """
    moment = as_of
    if moment.tzinfo is None:
        from datetime import UTC

        moment = moment.replace(tzinfo=UTC)
    else:
        from datetime import UTC

        moment = moment.astimezone(UTC)

    # Weekends → off hours (market closed — not a session-preference block)
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
    if h >= 21.0 or h < 6.0:
        return MarketSession.SYDNEY
    return MarketSession.OFF_HOURS


@dataclass(frozen=True, slots=True)
class SessionFilter:
    """Gate entries to open market sessions; soft-weight by session quality."""

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

        stars = stars_for_session(active)
        quality = quality_score_for_stars(stars)
        # Absolute block only when session is not in the 24/7 tradable set
        # (weekend / off-hours / closed). Named sessions soft-weight only.
        allowed = active in self.config.allowed_sessions
        risk_mult = (
            risk_multiplier_for_stars(stars) if allowed else Decimal("0")
        )
        if allowed:
            reason = (
                f"Session {active.value} open for 24/7 desk "
                f"(*{stars}, quality={quality}, riskx={risk_mult})."
            )
        else:
            reason = (
                f"Session {active.value} is outside tradable market windows "
                f"(weekend/off-hours/closed) - no new entries."
            )
        return SessionFilterResult(
            session=active,
            allowed=allowed,
            reason=reason,
            quality_score=quality,
            risk_multiplier=risk_mult,
            stars=stars,
        )
