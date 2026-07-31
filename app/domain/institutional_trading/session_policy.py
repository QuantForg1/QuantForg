"""24/7 session policy — soft weighting, never session-only absolute blocks.

Named market sessions (Sydney / Tokyo / London / New York / Overlap) are
tradable. Weekend / off-hours / closed remain non-tradable because the market
window is closed — that is not a session-preference hard block.

Session quality influences confidence scoring and risk sizing only.
AI quality, spread, volatility, news, liquidity, and risk gates stay
authoritative for entry decisions.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.market_context.enums import MarketSession

# All continuously tradable FX/gold liquidity windows
TRADABLE_SESSIONS_24_7: tuple[MarketSession, ...] = (
    MarketSession.SYDNEY,
    MarketSession.TOKYO,
    MarketSession.LONDON,
    MarketSession.NEW_YORK,
    MarketSession.LONDON_NY_OVERLAP,
)

TRADABLE_SESSION_NAMES: tuple[str, ...] = tuple(s.value for s in TRADABLE_SESSIONS_24_7)

# Liquidity / aggression stars (1-5). Used for soft score + risk weight only.
SESSION_QUALITY_STARS: dict[str, int] = {
    MarketSession.LONDON.value: 5,
    MarketSession.NEW_YORK.value: 5,
    MarketSession.LONDON_NY_OVERLAP.value: 5,
    MarketSession.TOKYO.value: 2,
    MarketSession.SYDNEY.value: 2,
    MarketSession.OFF_HOURS.value: 1,
    MarketSession.CLOSED.value: 0,
    # Legacy alias used by some desks
    "asian": 2,
    "asia": 2,
}

_QUALITY_BY_STARS: dict[int, int] = {
    5: 100,
    4: 85,
    3: 70,
    2: 55,
    1: 40,
    0: 15,
}

_RISK_BY_STARS: dict[int, Decimal] = {
    5: Decimal("1.00"),
    4: Decimal("0.90"),
    3: Decimal("0.80"),
    2: Decimal("0.70"),
    1: Decimal("0.50"),
    0: Decimal("0"),
}


def normalize_session_key(session: str | MarketSession | None) -> str:
    if session is None:
        return MarketSession.OFF_HOURS.value
    if isinstance(session, MarketSession):
        return session.value
    return str(session).strip().lower().replace(" ", "_")


def stars_for_session(session: str | MarketSession | None) -> int:
    key = normalize_session_key(session)
    return int(SESSION_QUALITY_STARS.get(key, 1))


def quality_score_for_stars(stars: int) -> int:
    clamped = max(0, min(5, int(stars)))
    return int(_QUALITY_BY_STARS.get(clamped, 40))


def quality_score_for_session(session: str | MarketSession | None) -> int:
    return quality_score_for_stars(stars_for_session(session))


def risk_multiplier_for_stars(stars: int) -> Decimal:
    """Risk scale ≤ 1.0 — may reduce size in weaker sessions, never increase."""
    clamped = max(0, min(5, int(stars)))
    return _RISK_BY_STARS.get(clamped, Decimal("0.70"))


def risk_multiplier_for_session(session: str | MarketSession | None) -> Decimal:
    return risk_multiplier_for_stars(stars_for_session(session))


def is_tradable_market_session(session: str | MarketSession | None) -> bool:
    key = normalize_session_key(session)
    if key in {"asian", "asia"}:
        return True
    return key in TRADABLE_SESSION_NAMES
