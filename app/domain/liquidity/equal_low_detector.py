"""EqualLowDetector — cluster swing lows into EqualLows.

Why it exists
-------------
Identifies buy-side liquidity formed by two or more lows within a price
tolerance. Structural observation only — not a signal or indicator.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities._guards import require
from app.domain.liquidity.ids import equal_lows_id
from app.domain.liquidity.models import EqualLows
from app.domain.market_structure.enums import SwingKind
from app.domain.market_structure.models import SwingPoint
from app.domain.value_objects.market import Price


@dataclass(frozen=True, slots=True)
class EqualLowDetector:
    """Detect equal (or near-equal) swing lows."""

    tolerance: Decimal = Decimal("0")
    min_touches: int = 2

    def detect(self, swings: Sequence[SwingPoint]) -> tuple[EqualLows, ...]:
        """Return equal-low clusters from LOW swings, oldest→newest."""
        require(self.min_touches >= 2, "min_touches must be >= 2")
        require(self.tolerance >= 0, "tolerance must be non-negative")
        lows = [s for s in swings if s.kind == SwingKind.LOW]
        if len(lows) < self.min_touches:
            return ()

        used: set[int] = set()
        clusters: list[EqualLows] = []

        for i, anchor in enumerate(lows):
            if i in used:
                continue
            members = [anchor]
            member_idx = [i]
            for j in range(i + 1, len(lows)):
                if j in used:
                    continue
                other = lows[j]
                if abs(other.price.value - anchor.price.value) <= self.tolerance:
                    members.append(other)
                    member_idx.append(j)

            if len(members) < self.min_touches:
                continue

            for idx in member_idx:
                used.add(idx)

            bar_indices = tuple(m.bar_index for m in members)
            timestamps = tuple(m.timestamp for m in members)
            price = members[0].price
            symbol = str(members[0].symbol_code)
            tf = members[0].timeframe.value
            clusters.append(
                EqualLows(
                    symbol_code=members[0].symbol_code,
                    timeframe=members[0].timeframe,
                    price=Price.of(price.value),
                    bar_indices=bar_indices,
                    timestamps=timestamps,
                    tolerance=self.tolerance,
                    id=equal_lows_id(symbol, tf, str(price), bar_indices),
                )
            )

        return tuple(clusters)
