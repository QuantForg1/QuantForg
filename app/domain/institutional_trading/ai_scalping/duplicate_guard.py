"""Duplicate / add-on trade guard for multi-position scalping."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AddTradeDecision:
    allow: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"allow": self.allow, "reason": self.reason}


def may_add_scalping_trade(
    *,
    open_positions: int,
    max_open: int,
    new_confidence: int,
    best_open_confidence: int | None,
    new_direction: str,
    open_directions: tuple[str, ...] = (),
    entry: Decimal | None = None,
    open_entries: tuple[Decimal, ...] = (),
    min_entry_distance: Decimal | None = None,
    require_improvement: bool = True,
    min_confidence_delta: int = 3,
) -> AddTradeDecision:
    """Allow another trade only within caps and when probability improves."""
    if open_positions >= max_open:
        return AddTradeDecision(
            False,
            f"Open positions {open_positions} at max {max_open}",
        )
    if open_positions <= 0:
        return AddTradeDecision(True, "No open positions — entry allowed")

    # Never duplicate identical direction + near-identical entry
    dir_u = (new_direction or "").upper()
    if dir_u and dir_u in {d.upper() for d in open_directions}:
        if entry is not None and open_entries and min_entry_distance is not None:
            for existing in open_entries:
                if abs(existing - entry) < min_entry_distance:
                    return AddTradeDecision(
                        False,
                        f"Duplicate entry near {existing} (min distance {min_entry_distance})",
                    )
        elif entry is not None and open_entries:
            for existing in open_entries:
                if existing == entry:
                    return AddTradeDecision(False, f"Identical entry {entry}")

    if require_improvement and best_open_confidence is not None:
        if new_confidence < best_open_confidence + min_confidence_delta:
            return AddTradeDecision(
                False,
                (
                    f"Confidence {new_confidence} does not improve on open "
                    f"best {best_open_confidence} by ≥{min_confidence_delta}"
                ),
            )

    return AddTradeDecision(True, "Probability improved — add-on allowed")
