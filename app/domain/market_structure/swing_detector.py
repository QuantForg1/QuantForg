"""SwingDetector — fractal pivot high/low detection.

Why it exists
-------------
Identifies confirmed local extremes from OHLC bars using a symmetric
left/right window. This is structural pivot detection, **not** a classic
lagging indicator (RSI/MACD/etc.) and produces no trade signals.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid5

from app.domain.entities._guards import require
from app.domain.exceptions.base import ValidationError
from app.domain.market_data.candle import Candle
from app.domain.market_structure.enums import SwingKind
from app.domain.market_structure.models import SwingPoint

# Stable namespace for deterministic swing identities across analysis runs.
_SWING_NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


@dataclass(frozen=True, slots=True)
class SwingDetector:
    """Detect swing highs and lows implementing :class:`SwingDetectorPort`."""

    def detect(
        self,
        candles: Sequence[Candle],
        *,
        left: int = 2,
        right: int = 2,
    ) -> tuple[SwingPoint, ...]:
        """Return confirmed swings using fractal strength ``left`` / ``right``."""
        require(left >= 1, "left must be >= 1", left=left)
        require(right >= 1, "right must be >= 1", right=right)
        if not candles:
            return ()

        self._assert_homogeneous(candles)
        n = len(candles)
        if n < left + right + 1:
            return ()

        symbol = candles[0].symbol_code
        timeframe = candles[0].timeframe
        swings: list[SwingPoint] = []

        for i in range(left, n - right):
            candle = candles[i]
            high = candle.high.value
            low = candle.low.value

            is_swing_high = all(
                high > candles[i - j].high.value for j in range(1, left + 1)
            ) and all(high > candles[i + j].high.value for j in range(1, right + 1))

            is_swing_low = all(
                low < candles[i - j].low.value for j in range(1, left + 1)
            ) and all(low < candles[i + j].low.value for j in range(1, right + 1))

            # Prefer a single label if a bar is both (rare with strict >/<).
            if is_swing_high:
                swings.append(
                    SwingPoint.create(
                        symbol_code=symbol,
                        timeframe=timeframe,
                        kind=SwingKind.HIGH,
                        price=candle.high,
                        bar_index=i,
                        timestamp=candle.close_time,
                        strength=min(left, right),
                        entity_id=self._swing_id(
                            symbol.value, timeframe.value, i, SwingKind.HIGH
                        ),
                    )
                )
            elif is_swing_low:
                swings.append(
                    SwingPoint.create(
                        symbol_code=symbol,
                        timeframe=timeframe,
                        kind=SwingKind.LOW,
                        price=candle.low,
                        bar_index=i,
                        timestamp=candle.close_time,
                        strength=min(left, right),
                        entity_id=self._swing_id(
                            symbol.value, timeframe.value, i, SwingKind.LOW
                        ),
                    )
                )

        return tuple(swings)

    @staticmethod
    def _swing_id(
        symbol: str,
        timeframe: str,
        bar_index: int,
        kind: SwingKind,
    ) -> UUID:
        return uuid5(
            _SWING_NAMESPACE,
            f"{symbol}:{timeframe}:{bar_index}:{kind.value}",
        )

    @staticmethod
    def _assert_homogeneous(candles: Sequence[Candle]) -> None:
        first = candles[0]
        for candle in candles[1:]:
            if (
                candle.symbol_code != first.symbol_code
                or candle.timeframe != first.timeframe
            ):
                raise ValidationError(
                    "All candles must share symbol_code and timeframe",
                    details={
                        "expected_symbol": str(first.symbol_code),
                        "expected_timeframe": first.timeframe.value,
                    },
                )
        for i in range(1, len(candles)):
            if candles[i].open_time < candles[i - 1].open_time:
                raise ValidationError(
                    "Candles must be ordered oldest to newest",
                    details={"index": i},
                )
