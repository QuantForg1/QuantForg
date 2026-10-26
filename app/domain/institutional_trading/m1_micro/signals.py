"""M1 setup detection. Patterns propose a stop and a target. They do not size."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Bar:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True, slots=True)
class Setup:
    name: str
    side: str
    stop: Decimal
    target: Decimal
    signal_id: str


def true_ranges(bars: list[Bar]) -> list[Decimal]:
    ranges: list[Decimal] = []
    previous_close: Decimal | None = None
    for bar in bars:
        span = bar.high - bar.low
        if previous_close is not None:
            span = max(
                span,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        ranges.append(span)
        previous_close = bar.close
    return ranges


def volatility_block(bars: list[Bar], *, spread: Decimal) -> str | None:
    """Reject quiet markets that cannot clear the spread, and reject spikes."""
    if len(bars) < 14:
        return "volatility_insufficient_bars"
    ranges = true_ranges(bars)[-14:]
    atr = sum(ranges, Decimal("0")) / Decimal(len(ranges))
    if atr <= spread * 3:
        return "volatility_too_quiet_for_cost"
    latest = ranges[-1]
    if latest > atr * 4:
        return "volatility_spike"
    return None


def _rising(bars: list[Bar]) -> bool:
    return bars[0].close < bars[1].close < bars[2].close


def _falling(bars: list[Bar]) -> bool:
    return bars[0].close > bars[1].close > bars[2].close


def detect_setup(
    bars: list[Bar],
    *,
    higher_timeframe_bias: str,
    spread: Decimal,
) -> Setup | None:
    """First matching setup, or None.

    ``higher_timeframe_bias`` is ``up``, ``down``, or ``flat``. A directional
    setup is taken only when the higher timeframe agrees. Flat does not confirm.
    """
    if len(bars) < 8:
        return None
    bias = (higher_timeframe_bias or "").strip().lower()
    if volatility_block(bars, spread=spread):
        return None
    recent = bars[-3:]
    lookback = bars[-8:-1]
    last = bars[-1]
    if bias == "up" and _rising(recent):
        stop = min(bar.low for bar in recent)
        span = last.close - stop
        if span > spread:
            return Setup(
                name="momentum_continuation",
                side="BUY",
                stop=stop,
                target=last.close + span,
                signal_id=f"mom-buy-{last.close}",
            )
    if bias == "down" and _falling(recent):
        stop = max(bar.high for bar in recent)
        span = stop - last.close
        if span > spread:
            return Setup(
                name="momentum_continuation",
                side="SELL",
                stop=stop,
                target=last.close - span,
                signal_id=f"mom-sell-{last.close}",
            )
    impulse = bars[-4:-1]
    pullback_buy = (
        bias == "up"
        and _rising(impulse)
        and last.low < impulse[-1].low
        and last.close > impulse[-1].close
    )
    if pullback_buy:
        swing = impulse[0].low
        if last.close - swing > spread:
            return Setup(
                name="pullback_continuation",
                side="BUY",
                stop=min(last.low, swing),
                target=last.close + (last.close - swing),
                signal_id=f"pull-buy-{last.close}",
            )
    prior_high = max(bar.high for bar in lookback)
    prior_low = min(bar.low for bar in lookback)
    if bias == "up" and last.close > prior_high:
        span = last.close - prior_high
        if span > spread:
            return Setup(
                name="range_breakout",
                side="BUY",
                stop=prior_high,
                target=last.close + span,
                signal_id=f"brk-buy-{last.close}",
            )
    if bias == "down" and last.close < prior_low:
        span = prior_low - last.close
        if span > spread:
            return Setup(
                name="range_breakout",
                side="SELL",
                stop=prior_low,
                target=last.close - span,
                signal_id=f"brk-sell-{last.close}",
            )
    swept = bars[-2]
    extreme_low = min(bar.low for bar in bars[-8:-2])
    extreme_high = max(bar.high for bar in bars[-8:-2])
    if (
        bias == "up"
        and swept.low < extreme_low
        and swept.close > extreme_low
        and last.close > swept.close
    ):
        return Setup(
            name="confirmed_micro_reversal",
            side="BUY",
            stop=swept.low,
            target=last.close + (last.close - swept.low),
            signal_id=f"rev-buy-{last.close}",
        )
    if (
        bias == "down"
        and swept.high > extreme_high
        and swept.close < extreme_high
        and last.close < swept.close
    ):
        return Setup(
            name="confirmed_micro_reversal",
            side="SELL",
            stop=swept.high,
            target=last.close - (swept.high - last.close),
            signal_id=f"rev-sell-{last.close}",
        )
    return None
