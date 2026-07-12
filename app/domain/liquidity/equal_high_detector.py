"""EqualHighDetector — cluster swing highs into EqualHighs.

Why it exists
-------------
Identifies sell-side liquidity formed by two or more highs within a price
tolerance. Structural observation only — not a signal or indicator.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities._guards import require
from app.domain.liquidity.ids import equal_highs_id
from app.domain.liquidity.models import EqualHighs
from app.domain.market_structure.enums import SwingKind
from app.domain.market_structure.models import SwingPoint
from app.domain.value_objects.market import Price


@dataclass(frozen=True, slots=True)
class EqualHighDetector:
    """Detect equal (or near-equal) swing highs."""

    tolerance: Decimal = Decimal("0")
    min_touches: int = 2

    def detect(self, swings: Sequence[SwingPoint]) -> tuple[EqualHighs, ...]:
        """Return equal-high clusters from HIGH swings, oldest→newest."""
        require(self.min_touches >= 2, "min_touches must be >= 2")
        require(self.tolerance >= 0, "tolerance must be non-negative")
        highs = [s for s in swings if s.kind == SwingKind.HIGH]
        if len(highs) < self.min_touches:
            return ()

        used: set[int] = set()
        clusters: list[EqualHighs] = []

        for i, anchor in enumerate(highs):
            if i in used:
                continue
            members = [anchor]
            member_idx = [i]
            for j in range(i + 1, len(highs)):
                if j in used:
                    continue
                other = highs[j]
                if abs(other.price.value - anchor.price.value) <= self.tolerance:
                    members.append(other)
                    member_idx.append(j)

            if len(members) < self.min_touches:
                continue

            for idx in member_idx:
                used.add(idx)

            bar_indices = tuple(m.bar_index for m in members)
            timestamps = tuple(m.timestamp for m in members)
            # Representative price: first touch (stable for identity).
            price = members[0].price
            symbol = str(members[0].symbol_code)
            tf = members[0].timeframe.value
            clusters.append(
                EqualHighs(
                    symbol_code=members[0].symbol_code,
                    timeframe=members[0].timeframe,
                    price=Price.of(price.value),
                    bar_indices=bar_indices,
                    timestamps=timestamps,
                    tolerance=self.tolerance,
                    id=equal_highs_id(symbol, tf, str(price), bar_indices),
                )
            )

        return tuple(clusters)
