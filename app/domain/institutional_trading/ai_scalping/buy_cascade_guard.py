"""Block same-direction BUY re-entry while a losing BUY's decline is unresolved.

A new lower break is not a new opportunity. Price must reclaim the failed
BUY entry, or M1/M5 must print a bullish CHOCH/BOS after that close.
Does not ban BUY, does not touch SELL, and does not invent a direction.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

BUY_CASCADE_REJECT = "BUY_CASCADE_UNRESOLVED_DECLINE"


def _event_time(event: Any) -> datetime | None:
    for name in ("broken_at", "timestamp", "time", "created_at"):
        raw = getattr(event, name, None)
        if isinstance(raw, datetime):
            return raw
    return None


def bullish_reversal_since(snapshot: Any, since: datetime | None) -> bool:
    """True when a bullish M1/M5 structure event is strictly after ``since``."""
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
                if structure_event_side(event) is not TradeDirection.BUY:
                    continue
                when = _event_time(event)
                if when is not None and when > since:
                    return True
    return False


def buy_cascade_blocked(
    *,
    direction: str,
    entry_price: Decimal | None,
    anchor: Decimal | None,
    reversal_confirmed: bool,
) -> tuple[bool, str]:
    """Return (blocked, reason). Missing prices fail open — never invent a block."""
    side = str(direction or "").strip().upper()
    if side != "BUY":
        return False, "not_buy"
    if anchor is None:
        return False, "no_losing_buy_anchor"
    if reversal_confirmed:
        return False, "bullish_reversal_confirmed"
    if entry_price is None:
        return False, "entry_unknown"
    try:
        entry = Decimal(str(entry_price))
        failed = Decimal(str(anchor))
    except Exception:
        return False, "price_unparseable"
    if entry > failed:
        return False, "reclaimed_failed_buy_entry"
    return True, BUY_CASCADE_REJECT
