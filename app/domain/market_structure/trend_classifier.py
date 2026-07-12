"""TrendClassifier — derive trend direction from structure roles.

Why it exists
-------------
Implements :class:`TrendAnalyzerPort` by inspecting recent HH/HL vs LH/LL
patterns. Produces a qualitative :class:`TrendState` — not an indicator and
not a trade signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import StructureRole, TrendDirection
from app.domain.market_structure.models import StructureNode, TrendState
from app.domain.value_objects.identity import SymbolCode

_BULLISH_ROLES = frozenset({StructureRole.HIGHER_HIGH, StructureRole.HIGHER_LOW})
_BEARISH_ROLES = frozenset({StructureRole.LOWER_HIGH, StructureRole.LOWER_LOW})


@dataclass(frozen=True, slots=True)
class TrendClassifier:
    """Classify structural trend from annotated swing nodes."""

    lookback: int = 6

    def classify(
        self,
        nodes: Sequence[StructureNode],
        *,
        symbol_code: SymbolCode,
        timeframe: Timeframe,
        as_of: datetime | None = None,
    ) -> TrendState:
        """Return trend state from the most recent structure roles."""
        moment = as_of or datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)

        if not nodes:
            return TrendState(
                symbol_code=symbol_code,
                timeframe=timeframe,
                direction=TrendDirection.UNKNOWN,
                as_of=moment,
                swing_count=0,
            )

        recent = list(nodes[-self.lookback :])
        roles = [n.role for n in recent if n.role != StructureRole.UNKNOWN]
        last_role = recent[-1].role

        if not roles:
            return TrendState(
                symbol_code=symbol_code,
                timeframe=timeframe,
                direction=TrendDirection.UNKNOWN,
                as_of=moment,
                last_structure_role=last_role,
                swing_count=len(nodes),
            )

        bullish = sum(1 for r in roles if r in _BULLISH_ROLES)
        bearish = sum(1 for r in roles if r in _BEARISH_ROLES)

        if bullish > bearish and bullish >= 2:
            direction = TrendDirection.UP
        elif bearish > bullish and bearish >= 2:
            direction = TrendDirection.DOWN
        elif bullish == 0 and bearish == 0:
            direction = TrendDirection.UNKNOWN
        else:
            direction = TrendDirection.RANGE

        return TrendState(
            symbol_code=symbol_code,
            timeframe=timeframe,
            direction=direction,
            as_of=moment,
            last_structure_role=last_role,
            swing_count=len(nodes),
        )
