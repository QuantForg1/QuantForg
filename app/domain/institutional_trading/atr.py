"""ATR (Average True Range) for ITE sizing — observational indicator only.

Does not alter strategy rules, risk %, min-lot policy, or OMS.
Matches the simple TR-window average used by production replay validation.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.market_data.candle import Candle

DEFAULT_ATR_PERIOD = 14


def compute_atr(
    candles: list[Candle] | tuple[Candle, ...],
    *,
    period: int = DEFAULT_ATR_PERIOD,
) -> Decimal | None:
    """Simple True-Range average over the last ``period`` bars.

    Requires at least 2 candles. Returns None when insufficient data.
    """
    if period < 1 or len(candles) < 2:
        return None
    trs: list[Decimal] = []
    prev_close = candles[0].close.value
    for c in candles[1:]:
        high = c.high.value
        low = c.low.value
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
        prev_close = c.close.value
    window = trs[-period:] if len(trs) >= period else trs
    if not window:
        return None
    return (sum(window, start=Decimal("0")) / Decimal(len(window))).quantize(
        Decimal("0.0001")
    )


def stop_distance_from_atr(
    atr: Decimal | None,
    *,
    multiplier: Decimal = Decimal("1.5"),
) -> Decimal | None:
    """Decision-pipeline stop distance: ``multiplier × ATR``."""
    if atr is None or atr <= 0:
        return None
    return (atr * multiplier).quantize(Decimal("0.0001"))
