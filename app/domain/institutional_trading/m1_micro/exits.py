"""Rule-based exits. A new entry requires a fresh signal after the thesis ends."""

from __future__ import annotations

from decimal import Decimal


def exit_reason(
    *,
    side: str,
    bid: Decimal,
    ask: Decimal,
    invalidation: Decimal,
    target: Decimal,
) -> str | None:
    """Return why the open thesis is over, or None while it is intact.

    Buy invalidates at the bid. Sell invalidates at the ask. The broker stop
    and target remain the hard exits; this is the same rule in price space.
    """
    side_u = (side or "").strip().upper()
    if side_u == "BUY":
        if bid <= invalidation:
            return "thesis_invalidated"
        if bid >= target:
            return "target_reached"
        return None
    if side_u == "SELL":
        if ask >= invalidation:
            return "thesis_invalidated"
        if ask <= target:
            return "target_reached"
        return None
    return "side_unknown"


def reentry_allowed(*, last_signal_id: str, signal_id: str, thesis_open: bool) -> bool:
    """A fresh id may enter only after the previous thesis has been closed."""
    current = (signal_id or "").strip()
    previous = (last_signal_id or "").strip()
    if thesis_open or not current:
        return False
    return current != previous
