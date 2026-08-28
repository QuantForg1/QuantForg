"""Session intelligence per asset class.

Crypto is 24/7. Forex / metals / indices / energy follow named sessions.
Never assume every market shares London-session behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.market_context.enums import MarketSession
from app.domain.market_universe.classification import classify_or_unknown
from app.domain.market_universe.constants import UNKNOWN

SESSION_LABELS = (
    "SYDNEY",
    "TOKYO",
    "LONDON",
    "LONDON-NY OVERLAP",
    "NEW YORK",
    "24/7",
)


def utc_hour(now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(UTC).hour


def named_session(now: datetime | None = None) -> str:
    """FX/metals/indices/energy session by UTC hour. Not a trading gate."""
    hour = utc_hour(now)
    # Approximate institutional windows (UTC). Research labels only.
    # Overlap 12-16 takes priority over standalone London / New York.
    if 12 <= hour < 16:
        return MarketSession.LONDON_NY_OVERLAP.value
    if 7 <= hour < 12:
        return MarketSession.LONDON.value
    if 16 <= hour < 21:
        return MarketSession.NEW_YORK.value
    if 0 <= hour < 7:
        return MarketSession.TOKYO.value
    return MarketSession.SYDNEY.value


def session_for_instrument(
    symbol: str | None,
    *,
    asset_class: str | None = None,
    now: datetime | None = None,
    broker_session: str | None = None,
) -> dict[str, Any]:
    cls = (asset_class or classify_or_unknown(symbol) or "OTHER").upper()
    if broker_session:
        label = str(broker_session).strip()
        return {
            "session": label,
            "session_source": "BROKER_METADATA",
            "asset_class": cls,
            "is_24_7": cls == "CRYPTO",
        }
    if cls == "CRYPTO":
        return {
            "session": "24/7",
            "session_source": "ASSET_PROFILE",
            "asset_class": cls,
            "is_24_7": True,
            "named_fx_session": named_session(now),
        }
    sess = named_session(now)
    pretty = {
        MarketSession.SYDNEY.value: "SYDNEY",
        MarketSession.TOKYO.value: "TOKYO",
        MarketSession.LONDON.value: "LONDON",
        MarketSession.LONDON_NY_OVERLAP.value: "LONDON-NY OVERLAP",
        MarketSession.NEW_YORK.value: "NEW YORK",
        MarketSession.CLOSED.value: "CLOSED",
        MarketSession.OFF_HOURS.value: "OFF_HOURS",
    }.get(sess, sess.upper())
    return {
        "session": pretty,
        "session_source": "SESSION_CALENDAR",
        "asset_class": cls,
        "is_24_7": False,
        "named_fx_session": sess,
    }


def weekend_behavior(asset_class: str | None) -> str:
    cls = str(asset_class or "").upper()
    if cls == "CRYPTO":
        return "24/7_CONTINUES"
    if cls in {"FOREX", "METALS", "INDICES", "ENERGY"}:
        return "TYPICALLY_CLOSED"
    return UNKNOWN
