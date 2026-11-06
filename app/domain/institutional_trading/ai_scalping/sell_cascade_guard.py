"""Block same-direction SELL re-entry while a losing SELL's rally is unresolved.

Symmetric to the BUY cascade: a new higher short is not a fresh opportunity.
Price must reclaim below the failed SELL entry, or M1/M5 must print a bearish
CHOCH/BOS after that close. Does not ban SELL forever, does not touch BUY,
and does not invent a direction.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

SELL_CASCADE_REJECT = "SELL_CASCADE_UNRESOLVED_RALLY"


def _event_time(event: Any) -> datetime | None:
    for name in ("broken_at", "timestamp", "time", "created_at"):
        raw = getattr(event, name, None)
        if isinstance(raw, datetime):
            return raw
    return None


def bearish_reversal_since(snapshot: Any, since: datetime | None) -> bool:
    """True when a bearish M1/M5 structure event is strictly after ``since``."""
    if snapshot is None or since is None:
        return False
    from app.domain.institutional_trading.ai_scalping.direction import (
        iter_scalp_structure_entries,
        structure_event_side,
    )
    from app.domain.institutional_trading.decision_models import TradeDirection

    for tf, structure in iter_scalp_structure_entries(snapshot):
        if tf not in {"M1", "M5"}:
            continue
        for name in ("changes_of_character", "breaks_of_structure"):
            events = getattr(structure, name, None)
            if not isinstance(events, (list, tuple)):
                continue
            for event in events:
                if structure_event_side(event) is not TradeDirection.SELL:
                    continue
                when = _event_time(event)
                if when is not None and when > since:
                    return True
    return False


def sell_cascade_blocked(
    *,
    direction: str,
    entry_price: Decimal | None,
    anchor: Decimal | None,
    reversal_confirmed: bool,
) -> tuple[bool, str]:
    """Return (blocked, reason). Missing prices fail open — never invent a block."""
    side = str(direction or "").strip().upper()
    if side != "SELL":
        return False, "not_sell"
    if anchor is None:
        return False, "no_losing_sell_anchor"
    if reversal_confirmed:
        return False, "bearish_reversal_confirmed"
    if entry_price is None:
        return False, "entry_unknown"
    try:
        entry = Decimal(str(entry_price))
        failed = Decimal(str(anchor))
    except Exception:
        return False, "price_unparseable"
    # Reclaim for a failed SELL means price traded back below the failed entry.
    if entry < failed:
        return False, "reclaimed_failed_sell_entry"
    return True, SELL_CASCADE_REJECT
