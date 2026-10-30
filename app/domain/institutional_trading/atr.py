"""ATR (Average True Range) for ITE sizing - observational indicator only.

Does not alter strategy rules, risk %, min-lot policy, or OMS.
Matches the simple TR-window average used by production replay validation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.domain.market_data.candle import Candle
from app.domain.market_data.closed_bars import as_utc, closed_analysis_bars
from app.domain.market_data.timeframe import Timeframe

# A series older than this many closed bars is not a fresh volatility input.
_MAX_STALE_BARS = 2

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
    # Mean of true ranges — do not quantize to 0.0001 (1 pip on 5-digit FX).
    # That gold-oriented rounding can push a passing 0.03% ATR% under the FX
    # hard floor when mid < 0.50. Stop distance still quantizes separately.
    mean = sum(window, start=Decimal("0")) / Decimal(len(window))
    return mean.quantize(Decimal("0.00000001"))


def stop_distance_from_atr(
    atr: Decimal | None,
    *,
    multiplier: Decimal = Decimal("1.5"),
) -> Decimal | None:
    """Decision-pipeline stop distance: ``multiplier x ATR``."""
    if atr is None or atr <= 0:
        return None
    return (atr * multiplier).quantize(Decimal("0.0001"))


def _positive(value: object) -> Decimal | None:
    if isinstance(value, Decimal):
        dec = value
    else:
        try:
            dec = Decimal(str(value))
        except Exception:
            return None
    if not dec.is_finite() or dec <= 0:
        return None
    return dec


def atr_for_timeframe(
    candles: list[Candle] | tuple[Candle, ...],
    *,
    as_of: datetime | None,
    timeframe: Timeframe,
) -> Decimal | None:
    """ATR of closed, aligned bars. None when that series is stale.

    Percentage gates and the owner stop must each call this with their own
    timeframe. A bar that is still open at ``as_of`` is excluded. A series
    whose newest close is older than two bars is rejected when the candle
    clock and ``as_of`` are comparable.
    """
    series = list(candles or [])
    if len(series) < 2:
        return None
    if as_of is None:
        return compute_atr(series)
    usable = closed_analysis_bars(series, as_of=as_of, timeframe=timeframe)
    if len(usable) < 2:
        return None
    moment = as_utc(as_of)
    newest = max(as_utc(c.close_time) for c in series)
    if newest <= moment + timeframe.duration:
        age = moment - max(as_utc(c.close_time) for c in usable)
        if age > timeframe.duration * _MAX_STALE_BARS:
            return None
    return compute_atr(usable)


def score_gate_atr(snapshot: object) -> Decimal | None:
    """ATR for the spread/ATR cap, the volatility band, and sniper distance.

    This is ``snapshot.atr`` (entry-confirmation timeframe). A missing value
    fails closed. The owner stop series is never substituted.
    """
    return _positive(getattr(snapshot, "atr", None))


def gate_atr_timeframe_label(config: object | None) -> str:
    """Timeframe label for the ATR that percentage gates actually score.

    Swing analysis stays on its M15 entry timeframe. Scalping reports the
    entry-confirmation timeframe (M5). This label does not select bars and
    does not change a gate.
    """
    tf = getattr(config, "entry_confirmation_tf", None)
    value = getattr(tf, "value", tf)
    text = str(value or "").strip().upper()
    return text or "M15"
