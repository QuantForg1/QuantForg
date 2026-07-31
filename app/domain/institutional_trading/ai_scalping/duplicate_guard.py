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
    open_profits: tuple[Decimal, ...] = (),
    require_unrealized_profit: bool = False,
    same_direction_profits: tuple[Decimal, ...] = (),
) -> AddTradeDecision:
    """Allow another trade only within caps and when probability improves.

    When ``require_unrealized_profit`` is True (PRE v2 pyramiding), add-ons
    require net unrealized profit on same-symbol / same-direction legs —
    never average into losing trades.
    """
    if open_positions >= max_open:
        return AddTradeDecision(
            False,
            f"Open positions {open_positions} at max {max_open}",
        )
    if open_positions <= 0:
        return AddTradeDecision(True, "No open positions — entry allowed")

    # Never average into losers / only pyramid into winners
    if require_unrealized_profit:
        legs = same_direction_profits or open_profits
        if legs:
            net = sum(legs, Decimal("0"))
            if net <= 0:
                return AddTradeDecision(
                    False,
                    (
                        f"Pyramiding blocked — unrealized P/L {net} ≤ 0 "
                        "(never average into losers)"
                    ),
                )
            if any(p <= 0 for p in legs):
                return AddTradeDecision(
                    False,
                    "Pyramiding blocked — losing leg present (scale winners only)",
                )

    # Never duplicate identical direction + near-identical entry
    dir_u = (new_direction or "").upper()
    if dir_u and dir_u in {d.upper() for d in open_directions}:
        if entry is not None and open_entries and min_entry_distance is not None:
            for existing in open_entries:
                if abs(existing - entry) < min_entry_distance:
                    return AddTradeDecision(
                        False,
                        f"Duplicate entry near {existing} (min distance {min_entry_distance})",  # noqa: E501
                    )
        elif entry is not None and open_entries:
            for existing in open_entries:
                if existing == entry:
                    return AddTradeDecision(False, f"Identical entry {entry}")

    if require_improvement and best_open_confidence is not None:  # noqa: SIM102
        if new_confidence < best_open_confidence + min_confidence_delta:
            return AddTradeDecision(
                False,
                (
                    f"Confidence {new_confidence} does not improve on open "
                    f"best {best_open_confidence} by ≥{min_confidence_delta}"
                ),
            )

    return AddTradeDecision(True, "Probability improved — add-on allowed")
