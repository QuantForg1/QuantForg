"""Additional deterministic strategy plugins.

Intentions only. Each rule uses the supplied OHLC bars. Missing volume or
bar time returns HOLD instead of a guessed price. These plugins do not
submit orders and do not change risk limits.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from app.domain.indicators import ema, rsi, sma
from app.domain.interfaces.strategy_engine import (
    EngineSignalAction,
    OhlcBar,
    SignalExplanation,
    StrategyIntention,
    StrategySnapshot,
)


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _ctx(snapshot: StrategySnapshot) -> str:
    return f"session={snapshot.session}; state={snapshot.market_state}"


def _param(params: dict[str, Any], key: str, default: Any) -> Any:
    return params.get(key, default)


def _hold(
    key: str,
    snapshot: StrategySnapshot,
    reason: str,
    indicator: str,
    threshold: str,
    value: str = "",
) -> StrategyIntention:
    return StrategyIntention(
        action=EngineSignalAction.HOLD,
        confidence=0.0,
        explanations=(
            SignalExplanation(
                reason=reason,
                indicator=indicator,
                threshold=threshold,
                market_context=_ctx(snapshot),
                value=value,
            ),
        ),
        strategy_key=key,
        symbol=snapshot.symbol,
        timeframe=snapshot.timeframe,
        timestamp=_now(),
    )


def _go(
    key: str,
    snapshot: StrategySnapshot,
    action: EngineSignalAction,
    confidence: float,
    reason: str,
    indicator: str,
    threshold: str,
    value: str,
) -> StrategyIntention:
    return StrategyIntention(
        action=action,
        confidence=round(min(0.85, max(0.5, confidence)), 3),
        explanations=(
            SignalExplanation(
                reason=reason,
                indicator=indicator,
                threshold=threshold,
                market_context=_ctx(snapshot),
                value=value,
            ),
        ),
        strategy_key=key,
        symbol=snapshot.symbol,
        timeframe=snapshot.timeframe,
        timestamp=_now(),
    )


def _period_ok(params: dict[str, Any], key: str, default: int, minimum: int = 2) -> tuple[bool, tuple[str, ...]]:
    try:
        period = int(_param(params, key, default))
    except (TypeError, ValueError):
        return False, (f"{key} must be an integer",)
    if period < minimum:
        return False, (f"{key} must be >= {minimum}",)
    return True, ()


def _atr(bars: tuple[OhlcBar, ...] | list[OhlcBar], period: int) -> float | None:
    if period < 1 or len(bars) < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, len(bars)):
        prev = bars[i - 1].close
        bar = bars[i]
        trs.append(max(bar.high - bar.low, abs(bar.high - prev), abs(bar.low - prev)))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def _has_volume(bars: tuple[OhlcBar, ...]) -> bool:
    return any(bar.volume > 0 for bar in bars)


def _hour(raw: str) -> int | None:
    text = raw.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.hour


class DonchianBreakoutStrategy:
    key: ClassVar[str] = "donchian_breakout"
    name: ClassVar[str] = "Donchian Breakout"
    category: ClassVar[str] = "breakout"
    description: ClassVar[str] = "Close breaks the prior N-bar high or low. The current bar is excluded from the channel."
    default_params: ClassVar[dict[str, Any]] = {"period": 20}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 20, 3)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 20))
        bars = snapshot.bars
        if len(bars) < period + 1:
            return _hold(self.key, snapshot, "Insufficient bars for Donchian channel", "Donchian", f"need>={period + 1}")
        prior = bars[-(period + 1) : -1]
        ceiling = max(bar.high for bar in prior)
        floor = min(bar.low for bar in prior)
        close = bars[-1].close
        if close > ceiling:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.62, "Close above the prior Donchian high", "Donchian", str(period), f"close={close:.5f}; high={ceiling:.5f}")
        if close < floor:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.62, "Close below the prior Donchian low", "Donchian", str(period), f"close={close:.5f}; low={floor:.5f}")
        return _hold(self.key, snapshot, "Close is inside the prior Donchian channel", "Donchian", str(period), f"close={close:.5f}")


class StochasticStrategy:
    key: ClassVar[str] = "stochastic"
    name: ClassVar[str] = "Stochastic"
    category: ClassVar[str] = "momentum"
    description: ClassVar[str] = "Stochastic %K crosses %D from the oversold or overbought zone."
    default_params: ClassVar[dict[str, Any]] = {"k_period": 14, "d_period": 3, "oversold": 20, "overbought": 80}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        ok, errors = _period_ok(params, "k_period", 14, 3)
        if not ok:
            return ok, errors
        return _period_ok(params, "d_period", 3, 2)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        k_period = int(_param(snapshot.params, "k_period", 14))
        d_period = int(_param(snapshot.params, "d_period", 3))
        oversold = float(_param(snapshot.params, "oversold", 20))
        overbought = float(_param(snapshot.params, "overbought", 80))
        bars = snapshot.bars
        need = k_period + d_period
        if len(bars) < need:
            return _hold(self.key, snapshot, "Insufficient bars for stochastic", "Stochastic", f"need>={need}")
        ks: list[float] = []
        for end in range(k_period - 1, len(bars)):
            window = bars[end - k_period + 1 : end + 1]
            highest = max(bar.high for bar in window)
            lowest = min(bar.low for bar in window)
            span = highest - lowest
            ks.append(50.0 if span == 0 else (window[-1].close - lowest) / span * 100.0)
        if len(ks) < d_period + 1:
            return _hold(self.key, snapshot, "Stochastic %D is not ready", "Stochastic", str(d_period))
        d_now = sum(ks[-d_period:]) / d_period
        d_prev = sum(ks[-d_period - 1 : -1]) / d_period
        k_now, k_prev = ks[-1], ks[-2]
        if k_prev <= d_prev and k_now > d_now and k_prev <= oversold:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.6, "Stochastic crossed up from oversold", "Stochastic", str(oversold), f"k={k_now:.2f}; d={d_now:.2f}")
        if k_prev >= d_prev and k_now < d_now and k_prev >= overbought:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.6, "Stochastic crossed down from overbought", "Stochastic", str(overbought), f"k={k_now:.2f}; d={d_now:.2f}")
        return _hold(self.key, snapshot, "No stochastic cross in an extreme zone", "Stochastic", f"{oversold}/{overbought}", f"k={k_now:.2f}")


class CciStrategy:
    key: ClassVar[str] = "cci"
    name: ClassVar[str] = "CCI"
    category: ClassVar[str] = "momentum"
    description: ClassVar[str] = "Commodity Channel Index leaves the +/-100 zone back toward zero."
    default_params: ClassVar[dict[str, Any]] = {"period": 20, "threshold": 100}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 20, 5)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 20))
        threshold = float(_param(snapshot.params, "threshold", 100))
        bars = snapshot.bars
        if len(bars) < period + 1:
            return _hold(self.key, snapshot, "Insufficient bars for CCI", "CCI", f"need>={period + 1}")
        typical = [(bar.high + bar.low + bar.close) / 3 for bar in bars]

        def cci_at(end: int) -> float:
            window = typical[end - period + 1 : end + 1]
            mean = sum(window) / period
            mean_dev = sum(abs(value - mean) for value in window) / period
            if mean_dev == 0:
                return 0.0
            return (typical[end] - mean) / (0.015 * mean_dev)

        current = cci_at(len(bars) - 1)
        previous = cci_at(len(bars) - 2)
        if previous <= -threshold and current > -threshold:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.58, "CCI crossed back above the lower threshold", "CCI", str(threshold), f"cci={current:.2f}")
        if previous >= threshold and current < threshold:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.58, "CCI crossed back below the upper threshold", "CCI", str(threshold), f"cci={current:.2f}")
        return _hold(self.key, snapshot, "CCI did not leave an extreme", "CCI", str(threshold), f"cci={current:.2f}")


class WilliamsRStrategy:
    key: ClassVar[str] = "williams_r"
    name: ClassVar[str] = "Williams %R"
    category: ClassVar[str] = "momentum"
    description: ClassVar[str] = "Williams %R leaves oversold (-80) or overbought (-20)."
    default_params: ClassVar[dict[str, Any]] = {"period": 14}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 14, 3)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 14))
        bars = snapshot.bars
        if len(bars) < period + 1:
            return _hold(self.key, snapshot, "Insufficient bars for Williams %R", "Williams %R", f"need>={period + 1}")

        def wr(end: int) -> float:
            window = bars[end - period + 1 : end + 1]
            highest = max(bar.high for bar in window)
            lowest = min(bar.low for bar in window)
            span = highest - lowest
            if span == 0:
                return -50.0
            return (highest - window[-1].close) / span * -100.0

        current = wr(len(bars) - 1)
        previous = wr(len(bars) - 2)
        if previous <= -80 and current > -80:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.58, "Williams %R left oversold", "Williams %R", "-80", f"wr={current:.2f}")
        if previous >= -20 and current < -20:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.58, "Williams %R left overbought", "Williams %R", "-20", f"wr={current:.2f}")
        return _hold(self.key, snapshot, "Williams %R stayed inside the band", "Williams %R", "-80/-20", f"wr={current:.2f}")


class AdxTrendStrategy:
    key: ClassVar[str] = "adx_trend"
    name: ClassVar[str] = "ADX Trend"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "Buy when +DI is above -DI and ADX is at least the threshold. Sell on the opposite."
    default_params: ClassVar[dict[str, Any]] = {"period": 14, "adx_min": 20}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 14, 5)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 14))
        adx_min = float(_param(snapshot.params, "adx_min", 20))
        bars = snapshot.bars
        if len(bars) < period * 2 + 2:
            return _hold(self.key, snapshot, "Insufficient bars for ADX", "ADX", f"need>={period * 2 + 2}")
        plus_dm: list[float] = []
        minus_dm: list[float] = []
        trs: list[float] = []
        for i in range(1, len(bars)):
            up = bars[i].high - bars[i - 1].high
            down = bars[i - 1].low - bars[i].low
            plus_dm.append(up if up > down and up > 0 else 0.0)
            minus_dm.append(down if down > up and down > 0 else 0.0)
            prev = bars[i - 1].close
            trs.append(max(bars[i].high - bars[i].low, abs(bars[i].high - prev), abs(bars[i].low - prev)))
        atr_sum = sum(trs[-period:])
        if atr_sum == 0:
            return _hold(self.key, snapshot, "ATR is zero", "ADX", str(period))
        plus_di = 100 * sum(plus_dm[-period:]) / atr_sum
        minus_di = 100 * sum(minus_dm[-period:]) / atr_sum
        denom = plus_di + minus_di
        dx = 0.0 if denom == 0 else 100 * abs(plus_di - minus_di) / denom
        if dx < adx_min:
            return _hold(self.key, snapshot, "ADX is below the trend threshold", "ADX", str(adx_min), f"adx={dx:.2f}")
        if plus_di > minus_di:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.55 + min(0.25, dx / 200), "+DI leads and ADX confirms a trend", "ADX", str(adx_min), f"adx={dx:.2f}; +di={plus_di:.2f}; -di={minus_di:.2f}")
        if minus_di > plus_di:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.55 + min(0.25, dx / 200), "-DI leads and ADX confirms a trend", "ADX", str(adx_min), f"adx={dx:.2f}; +di={plus_di:.2f}; -di={minus_di:.2f}")
        return _hold(self.key, snapshot, "+DI and -DI are equal", "ADX", str(adx_min), f"adx={dx:.2f}")


class SupertrendStrategy:
    key: ClassVar[str] = "supertrend"
    name: ClassVar[str] = "Supertrend"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "ATR supertrend flips when close crosses the opposite band."
    default_params: ClassVar[dict[str, Any]] = {"period": 10, "multiplier": 3}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        ok, errors = _period_ok(params, "period", 10, 3)
        if not ok:
            return ok, errors
        if float(_param(params, "multiplier", 3)) <= 0:
            return False, ("multiplier must be > 0",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 10))
        multiplier = float(_param(snapshot.params, "multiplier", 3))
        bars = snapshot.bars
        if len(bars) < period + 3:
            return _hold(self.key, snapshot, "Insufficient bars for supertrend", "Supertrend", f"need>={period + 3}")
        trend = 1
        final_upper: float | None = None
        final_lower: float | None = None
        for i in range(period + 1, len(bars)):
            atr_value = _atr(bars[: i + 1], period)
            if atr_value is None:
                continue
            mid = (bars[i].high + bars[i].low) / 2
            basic_upper = mid + multiplier * atr_value
            basic_lower = mid - multiplier * atr_value
            if final_upper is None or basic_upper < final_upper or bars[i - 1].close > final_upper:
                final_upper = basic_upper
            if final_lower is None or basic_lower > final_lower or bars[i - 1].close < final_lower:
                final_lower = basic_lower
            if trend == 1 and bars[i].close < final_lower:
                trend = -1
            elif trend == -1 and bars[i].close > final_upper:
                trend = 1
        action = EngineSignalAction.BUY if trend == 1 else EngineSignalAction.SELL
        return _go(self.key, snapshot, action, 0.6, "Supertrend direction from the ATR bands", "Supertrend", f"{period}x{multiplier}", f"trend={trend}")


class KeltnerChannelStrategy:
    key: ClassVar[str] = "keltner_channel"
    name: ClassVar[str] = "Keltner Channel"
    category: ClassVar[str] = "breakout"
    description: ClassVar[str] = "Close outside an EMA channel widened by ATR."
    default_params: ClassVar[dict[str, Any]] = {"period": 20, "multiplier": 2}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 20, 5)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 20))
        multiplier = float(_param(snapshot.params, "multiplier", 2))
        closes = [bar.close for bar in snapshot.bars]
        line = ema(closes, period)
        atr_value = _atr(snapshot.bars, period)
        if line[-1] is None or atr_value is None:
            return _hold(self.key, snapshot, "Keltner channel is not ready", "Keltner", str(period))
        upper = line[-1] + multiplier * atr_value
        lower = line[-1] - multiplier * atr_value
        close = closes[-1]
        if close > upper:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.6, "Close above the Keltner upper band", "Keltner", str(period), f"close={close:.5f}; upper={upper:.5f}")
        if close < lower:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.6, "Close below the Keltner lower band", "Keltner", str(period), f"close={close:.5f}; lower={lower:.5f}")
        return _hold(self.key, snapshot, "Close is inside the Keltner channel", "Keltner", str(period), f"close={close:.5f}")


class TripleEmaStrategy:
    key: ClassVar[str] = "triple_ema"
    name: ClassVar[str] = "Triple EMA"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "Fast, mid, and slow EMAs are stacked in one direction."
    default_params: ClassVar[dict[str, Any]] = {"fast": 8, "mid": 21, "slow": 55}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        fast = int(_param(params, "fast", 8))
        mid = int(_param(params, "mid", 21))
        slow = int(_param(params, "slow", 55))
        if not (2 <= fast < mid < slow):
            return False, ("require 2 <= fast < mid < slow",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        fast = int(_param(snapshot.params, "fast", 8))
        mid = int(_param(snapshot.params, "mid", 21))
        slow = int(_param(snapshot.params, "slow", 55))
        closes = [bar.close for bar in snapshot.bars]
        fast_line = ema(closes, fast)
        mid_line = ema(closes, mid)
        slow_line = ema(closes, slow)
        if fast_line[-1] is None or mid_line[-1] is None or slow_line[-1] is None:
            return _hold(self.key, snapshot, "Triple EMA is not ready", "EMA", str(slow))
        if fast_line[-1] > mid_line[-1] > slow_line[-1]:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.64, "EMAs are stacked upward", "EMA", f"{fast}/{mid}/{slow}", f"fast={fast_line[-1]:.5f}")
        if fast_line[-1] < mid_line[-1] < slow_line[-1]:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.64, "EMAs are stacked downward", "EMA", f"{fast}/{mid}/{slow}", f"fast={fast_line[-1]:.5f}")
        return _hold(self.key, snapshot, "EMAs are not stacked", "EMA", f"{fast}/{mid}/{slow}")


class HullTrendStrategy:
    key: ClassVar[str] = "hull_trend"
    name: ClassVar[str] = "Hull Trend"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "Hull moving average slope and close on the same side."
    default_params: ClassVar[dict[str, Any]] = {"period": 16}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 16, 4)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 16))
        closes = [bar.close for bar in snapshot.bars]
        half = max(2, period // 2)
        root = max(2, int(period**0.5))
        if len(closes) < period + root:
            return _hold(self.key, snapshot, "Insufficient bars for Hull MA", "HMA", str(period))

        def wma(values: list[float], length: int) -> float | None:
            if len(values) < length:
                return None
            window = values[-length:]
            weight = length * (length + 1) / 2
            return sum(value * (index + 1) for index, value in enumerate(window)) / weight

        def hma_at(end: int) -> float | None:
            series = closes[: end + 1]
            fast = wma(series, half)
            slow = wma(series, period)
            if fast is None or slow is None:
                return None
            raw = 2 * fast - slow
            # Approximate the final WMA with the last raw point repeated is not used.
            # Build a short raw series from the last `root` ends.
            raws: list[float] = []
            start = max(period, end - root + 1)
            for cursor in range(start, end + 1):
                piece = closes[: cursor + 1]
                fast_i = wma(piece, half)
                slow_i = wma(piece, period)
                if fast_i is None or slow_i is None:
                    continue
                raws.append(2 * fast_i - slow_i)
            return wma(raws, min(root, len(raws))) if raws else raw

        current = hma_at(len(closes) - 1)
        previous = hma_at(len(closes) - 2)
        if current is None or previous is None:
            return _hold(self.key, snapshot, "Hull MA is not ready", "HMA", str(period))
        close = closes[-1]
        if current > previous and close > current:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.6, "Hull MA is rising and close is above it", "HMA", str(period), f"hma={current:.5f}")
        if current < previous and close < current:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.6, "Hull MA is falling and close is below it", "HMA", str(period), f"hma={current:.5f}")
        return _hold(self.key, snapshot, "Hull MA and close disagree", "HMA", str(period), f"hma={current:.5f}")


class AroonStrategy:
    key: ClassVar[str] = "aroon"
    name: ClassVar[str] = "Aroon"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "Aroon Up and Aroon Down show which extreme happened more recently."
    default_params: ClassVar[dict[str, Any]] = {"period": 25}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 25, 5)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 25))
        bars = snapshot.bars
        if len(bars) < period + 1:
            return _hold(self.key, snapshot, "Insufficient bars for Aroon", "Aroon", f"need>={period + 1}")
        window = bars[-(period + 1) :]
        highs = [bar.high for bar in window]
        lows = [bar.low for bar in window]
        since_high = len(highs) - 1 - highs.index(max(highs))
        since_low = len(lows) - 1 - lows.index(min(lows))
        up = 100 * (period - since_high) / period
        down = 100 * (period - since_low) / period
        if up >= 70 and down <= 30:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.6, "Aroon Up leads", "Aroon", str(period), f"up={up:.1f}; down={down:.1f}")
        if down >= 70 and up <= 30:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.6, "Aroon Down leads", "Aroon", str(period), f"up={up:.1f}; down={down:.1f}")
        return _hold(self.key, snapshot, "Aroon has no dominant side", "Aroon", str(period), f"up={up:.1f}; down={down:.1f}")


class AwesomeOscillatorStrategy:
    key: ClassVar[str] = "awesome_oscillator"
    name: ClassVar[str] = "Awesome Oscillator"
    category: ClassVar[str] = "momentum"
    description: ClassVar[str] = "5-period median-price average crosses the 34-period average."
    default_params: ClassVar[dict[str, Any]] = {"fast": 5, "slow": 34}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        fast = int(_param(params, "fast", 5))
        slow = int(_param(params, "slow", 34))
        if not (2 <= fast < slow):
            return False, ("require 2 <= fast < slow",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        fast = int(_param(snapshot.params, "fast", 5))
        slow = int(_param(snapshot.params, "slow", 34))
        medians = [(bar.high + bar.low) / 2 for bar in snapshot.bars]
        fast_line = sma(medians, fast)
        slow_line = sma(medians, slow)
        if fast_line[-1] is None or slow_line[-1] is None or fast_line[-2] is None or slow_line[-2] is None:
            return _hold(self.key, snapshot, "Awesome oscillator is not ready", "AO", f"{fast}/{slow}")
        prev = fast_line[-2] - slow_line[-2]
        current = fast_line[-1] - slow_line[-1]
        if prev <= 0 < current:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.6, "Awesome oscillator crossed above zero", "AO", "0", f"ao={current:.5f}")
        if prev >= 0 > current:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.6, "Awesome oscillator crossed below zero", "AO", "0", f"ao={current:.5f}")
        return _hold(self.key, snapshot, "Awesome oscillator did not cross zero", "AO", "0", f"ao={current:.5f}")


class EngulfingStrategy:
    key: ClassVar[str] = "engulfing"
    name: ClassVar[str] = "Engulfing"
    category: ClassVar[str] = "price_action"
    description: ClassVar[str] = "The latest candle body fully engulfs the previous opposite candle."
    default_params: ClassVar[dict[str, Any]] = {}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        if len(snapshot.bars) < 2:
            return _hold(self.key, snapshot, "Need two candles", "Engulfing", "2")
        prev, last = snapshot.bars[-2], snapshot.bars[-1]
        prev_bear = prev.close < prev.open
        prev_bull = prev.close > prev.open
        last_bull = last.close > last.open
        last_bear = last.close < last.open
        if prev_bear and last_bull and last.open <= prev.close and last.close >= prev.open:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.57, "Bullish engulfing candle", "Engulfing", "body", f"close={last.close:.5f}")
        if prev_bull and last_bear and last.open >= prev.close and last.close <= prev.open:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.57, "Bearish engulfing candle", "Engulfing", "body", f"close={last.close:.5f}")
        return _hold(self.key, snapshot, "No engulfing candle", "Engulfing", "body")


class PinBarStrategy:
    key: ClassVar[str] = "pin_bar"
    name: ClassVar[str] = "Pin Bar"
    category: ClassVar[str] = "price_action"
    description: ClassVar[str] = "A rejection wick at least twice the candle body, with the close in the rejection direction."
    default_params: ClassVar[dict[str, Any]] = {"wick_ratio": 2}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        if float(_param(params, "wick_ratio", 2)) < 1:
            return False, ("wick_ratio must be >= 1",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        ratio = float(_param(snapshot.params, "wick_ratio", 2))
        bar = snapshot.bars[-1]
        body = abs(bar.close - bar.open)
        span = bar.high - bar.low
        if span <= 0:
            return _hold(self.key, snapshot, "Candle has no range", "Pin bar", str(ratio))
        lower = min(bar.open, bar.close) - bar.low
        upper = bar.high - max(bar.open, bar.close)
        if lower >= ratio * max(body, span * 0.05) and upper <= max(body, span * 0.25) and bar.close >= bar.open:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.56, "Bullish pin bar", "Pin bar", str(ratio), f"lower={lower:.5f}")
        if upper >= ratio * max(body, span * 0.05) and lower <= max(body, span * 0.25) and bar.close <= bar.open:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.56, "Bearish pin bar", "Pin bar", str(ratio), f"upper={upper:.5f}")
        return _hold(self.key, snapshot, "No pin bar", "Pin bar", str(ratio))


class InsideBarBreakoutStrategy:
    key: ClassVar[str] = "inside_bar_breakout"
    name: ClassVar[str] = "Inside Bar Breakout"
    category: ClassVar[str] = "breakout"
    description: ClassVar[str] = "After an inside bar, close breaks the mother bar high or low."
    default_params: ClassVar[dict[str, Any]] = {}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        if len(snapshot.bars) < 3:
            return _hold(self.key, snapshot, "Need a mother bar, an inside bar, and a break bar", "Inside bar", "3")
        mother, inside, last = snapshot.bars[-3], snapshot.bars[-2], snapshot.bars[-1]
        if inside.high > mother.high or inside.low < mother.low:
            return _hold(self.key, snapshot, "The middle bar is not inside the mother bar", "Inside bar", "containment")
        if last.close > mother.high:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.6, "Close broke the mother bar high", "Inside bar", "high", f"close={last.close:.5f}")
        if last.close < mother.low:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.6, "Close broke the mother bar low", "Inside bar", "low", f"close={last.close:.5f}")
        return _hold(self.key, snapshot, "Inside bar has not broken", "Inside bar", "mother")


class RsiPullbackStrategy:
    key: ClassVar[str] = "rsi_pullback"
    name: ClassVar[str] = "RSI Pullback"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "RSI leaves 40 in the direction of the 50-period SMA."
    default_params: ClassVar[dict[str, Any]] = {"sma_period": 50, "rsi_period": 14}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "sma_period", 50, 10)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        sma_period = int(_param(snapshot.params, "sma_period", 50))
        rsi_period = int(_param(snapshot.params, "rsi_period", 14))
        closes = [bar.close for bar in snapshot.bars]
        average = sma(closes, sma_period)
        strength = rsi(closes, rsi_period)
        if average[-1] is None or strength[-1] is None or strength[-2] is None:
            return _hold(self.key, snapshot, "RSI pullback inputs are not ready", "RSI", str(rsi_period))
        close = closes[-1]
        if close > average[-1] and strength[-2] <= 40 < strength[-1]:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.61, "RSI turned up while price is above the SMA", "RSI", "40", f"rsi={strength[-1]:.2f}")
        if close < average[-1] and strength[-2] >= 60 > strength[-1]:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.61, "RSI turned down while price is below the SMA", "RSI", "60", f"rsi={strength[-1]:.2f}")
        return _hold(self.key, snapshot, "No RSI pullback with the SMA", "RSI", "40/60", f"rsi={strength[-1]:.2f}")


class BollingerSqueezeStrategy:
    key: ClassVar[str] = "bollinger_squeeze"
    name: ClassVar[str] = "Bollinger Squeeze"
    category: ClassVar[str] = "breakout"
    description: ClassVar[str] = "Bandwidth was compressed, then close left the band."
    default_params: ClassVar[dict[str, Any]] = {"period": 20, "num_std": 2, "squeeze": 0.05}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 20, 5)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 20))
        num_std = float(_param(snapshot.params, "num_std", 2))
        squeeze = float(_param(snapshot.params, "squeeze", 0.05))
        closes = [bar.close for bar in snapshot.bars]
        if len(closes) < period + 2:
            return _hold(self.key, snapshot, "Insufficient bars for a squeeze", "Bollinger", str(period))

        def band(end: int) -> tuple[float, float, float] | None:
            window = closes[end - period + 1 : end + 1]
            mean = sum(window) / period
            if mean == 0:
                return None
            std = (sum((value - mean) ** 2 for value in window) / period) ** 0.5
            return mean + num_std * std, mean - num_std * std, (2 * num_std * std) / abs(mean)

        current = band(len(closes) - 1)
        previous = band(len(closes) - 2)
        if current is None or previous is None:
            return _hold(self.key, snapshot, "Band could not be computed", "Bollinger", str(period))
        if previous[2] > squeeze:
            return _hold(self.key, snapshot, "Prior bandwidth was not compressed", "Bollinger", str(squeeze), f"width={previous[2]:.4f}")
        close = closes[-1]
        if close > current[0]:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.63, "Close left a squeezed band upward", "Bollinger", str(squeeze), f"close={close:.5f}")
        if close < current[1]:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.63, "Close left a squeezed band downward", "Bollinger", str(squeeze), f"close={close:.5f}")
        return _hold(self.key, snapshot, "Squeeze has not broken", "Bollinger", str(squeeze))


class IchimokuStrategy:
    key: ClassVar[str] = "ichimoku"
    name: ClassVar[str] = "Ichimoku"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "Close is above the unshifted cloud and Tenkan is above Kijun, or the bearish mirror. The cloud is not shifted forward."
    default_params: ClassVar[dict[str, Any]] = {"tenkan": 9, "kijun": 26, "span": 52}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        tenkan = int(_param(params, "tenkan", 9))
        kijun = int(_param(params, "kijun", 26))
        span = int(_param(params, "span", 52))
        if not (2 <= tenkan < kijun <= span):
            return False, ("require 2 <= tenkan < kijun <= span",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        tenkan_n = int(_param(snapshot.params, "tenkan", 9))
        kijun_n = int(_param(snapshot.params, "kijun", 26))
        span_n = int(_param(snapshot.params, "span", 52))
        bars = snapshot.bars
        if len(bars) < span_n:
            return _hold(self.key, snapshot, "Insufficient bars for Ichimoku", "Ichimoku", str(span_n))

        def mid(length: int) -> float:
            window = bars[-length:]
            return (max(bar.high for bar in window) + min(bar.low for bar in window)) / 2

        tenkan = mid(tenkan_n)
        kijun = mid(kijun_n)
        span_a = (tenkan + kijun) / 2
        span_b = mid(span_n)
        cloud_top = max(span_a, span_b)
        cloud_bottom = min(span_a, span_b)
        close = bars[-1].close
        if close > cloud_top and tenkan > kijun:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.64, "Price is above the cloud and Tenkan leads Kijun", "Ichimoku", f"{tenkan_n}/{kijun_n}/{span_n}", f"close={close:.5f}")
        if close < cloud_bottom and tenkan < kijun:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.64, "Price is below the cloud and Tenkan is under Kijun", "Ichimoku", f"{tenkan_n}/{kijun_n}/{span_n}", f"close={close:.5f}")
        return _hold(self.key, snapshot, "Price is not aligned with the cloud", "Ichimoku", f"{tenkan_n}/{kijun_n}/{span_n}", f"close={close:.5f}")


class HeikinAshiTrendStrategy:
    key: ClassVar[str] = "heikin_ashi_trend"
    name: ClassVar[str] = "Heikin Ashi Trend"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "The last three Heikin Ashi candles agree on direction."
    default_params: ClassVar[dict[str, Any]] = {"bars": 3}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "bars", 3, 2)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        count = int(_param(snapshot.params, "bars", 3))
        bars = snapshot.bars
        if len(bars) < count + 1:
            return _hold(self.key, snapshot, "Insufficient bars for Heikin Ashi", "Heikin Ashi", str(count))
        ha_open = (bars[0].open + bars[0].close) / 2
        candles: list[tuple[float, float]] = []
        for bar in bars:
            ha_close = (bar.open + bar.high + bar.low + bar.close) / 4
            candles.append((ha_open, ha_close))
            ha_open = (ha_open + ha_close) / 2
        recent = candles[-count:]
        if all(close > open_ for open_, close in recent):
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.58, "Heikin Ashi candles are bullish", "Heikin Ashi", str(count), f"close={recent[-1][1]:.5f}")
        if all(close < open_ for open_, close in recent):
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.58, "Heikin Ashi candles are bearish", "Heikin Ashi", str(count), f"close={recent[-1][1]:.5f}")
        return _hold(self.key, snapshot, "Heikin Ashi candles disagree", "Heikin Ashi", str(count))


class LinearRegressionStrategy:
    key: ClassVar[str] = "linear_regression"
    name: ClassVar[str] = "Linear Regression"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "Ordinary least-squares slope of closes, with close on the same side of the mean."
    default_params: ClassVar[dict[str, Any]] = {"period": 20}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 20, 5)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 20))
        closes = [bar.close for bar in snapshot.bars[-period:]]
        if len(closes) < period:
            return _hold(self.key, snapshot, "Insufficient bars for regression", "LinReg", str(period))
        mean_x = (period - 1) / 2
        mean_y = sum(closes) / period
        denom = sum((index - mean_x) ** 2 for index in range(period))
        if denom == 0:
            return _hold(self.key, snapshot, "Regression denominator is zero", "LinReg", str(period))
        slope = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(closes)) / denom
        close = closes[-1]
        if slope > 0 and close > mean_y:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.58, "Regression slope is positive", "LinReg", str(period), f"slope={slope:.6f}")
        if slope < 0 and close < mean_y:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.58, "Regression slope is negative", "LinReg", str(period), f"slope={slope:.6f}")
        return _hold(self.key, snapshot, "Slope and close disagree", "LinReg", str(period), f"slope={slope:.6f}")


class ZScoreReversionStrategy:
    key: ClassVar[str] = "zscore_reversion"
    name: ClassVar[str] = "Z-Score Reversion"
    category: ClassVar[str] = "mean_reversion"
    description: ClassVar[str] = "Close z-score versus its SMA is beyond the threshold."
    default_params: ClassVar[dict[str, Any]] = {"period": 20, "threshold": 2}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        ok, errors = _period_ok(params, "period", 20, 5)
        if not ok:
            return ok, errors
        if float(_param(params, "threshold", 2)) <= 0:
            return False, ("threshold must be > 0",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 20))
        threshold = float(_param(snapshot.params, "threshold", 2))
        closes = [bar.close for bar in snapshot.bars[-period:]]
        if len(closes) < period:
            return _hold(self.key, snapshot, "Insufficient bars for z-score", "Z-score", str(period))
        mean = sum(closes) / period
        variance = sum((value - mean) ** 2 for value in closes) / period
        std = variance**0.5
        if std == 0:
            return _hold(self.key, snapshot, "Standard deviation is zero", "Z-score", str(period))
        score = (closes[-1] - mean) / std
        if score <= -threshold:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.6, "Close is stretched below the mean", "Z-score", str(threshold), f"z={score:.2f}")
        if score >= threshold:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.6, "Close is stretched above the mean", "Z-score", str(threshold), f"z={score:.2f}")
        return _hold(self.key, snapshot, "Z-score is inside the band", "Z-score", str(threshold), f"z={score:.2f}")


class Nr7BreakoutStrategy:
    key: ClassVar[str] = "nr7_breakout"
    name: ClassVar[str] = "NR7 Breakout"
    category: ClassVar[str] = "breakout"
    description: ClassVar[str] = "The previous bar was the narrowest of seven, and the latest close breaks it."
    default_params: ClassVar[dict[str, Any]] = {}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        bars = snapshot.bars
        if len(bars) < 8:
            return _hold(self.key, snapshot, "Need eight bars for NR7", "NR7", "8")
        completed = bars[-8:-1]
        ranges = [bar.high - bar.low for bar in completed]
        if ranges[-1] > min(ranges):
            return _hold(self.key, snapshot, "The previous bar is not the narrowest of seven", "NR7", "range")
        narrow = completed[-1]
        close = bars[-1].close
        if close > narrow.high:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.6, "Close broke the NR7 high", "NR7", "high", f"close={close:.5f}")
        if close < narrow.low:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.6, "Close broke the NR7 low", "NR7", "low", f"close={close:.5f}")
        return _hold(self.key, snapshot, "NR7 bar has not broken", "NR7", "range")


class ThreeBarReversalStrategy:
    key: ClassVar[str] = "three_bar_reversal"
    name: ClassVar[str] = "Three Bar Reversal"
    category: ClassVar[str] = "price_action"
    description: ClassVar[str] = "Two pushes one way, then a close through the prior bar in the other direction."
    default_params: ClassVar[dict[str, Any]] = {}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        if len(snapshot.bars) < 3:
            return _hold(self.key, snapshot, "Need three bars", "Three bar", "3")
        first, second, third = snapshot.bars[-3:]
        if second.close < first.close and third.close > second.high:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.57, "Close reversed through the prior high", "Three bar", "high", f"close={third.close:.5f}")
        if second.close > first.close and third.close < second.low:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.57, "Close reversed through the prior low", "Three bar", "low", f"close={third.close:.5f}")
        return _hold(self.key, snapshot, "No three-bar reversal", "Three bar", "3")


class GapFillStrategy:
    key: ClassVar[str] = "gap_fill"
    name: ClassVar[str] = "Gap Fill"
    category: ClassVar[str] = "mean_reversion"
    description: ClassVar[str] = "The open gaps away from the previous close and the latest close moves back toward it."
    default_params: ClassVar[dict[str, Any]] = {"min_gap_pct": 0.15}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        if float(_param(params, "min_gap_pct", 0.15)) < 0:
            return False, ("min_gap_pct must be >= 0",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        if len(snapshot.bars) < 2:
            return _hold(self.key, snapshot, "Need a previous close", "Gap", "2")
        prev, last = snapshot.bars[-2], snapshot.bars[-1]
        if prev.close == 0:
            return _hold(self.key, snapshot, "Previous close is zero", "Gap", "close")
        gap_pct = (last.open - prev.close) / abs(prev.close) * 100
        minimum = float(_param(snapshot.params, "min_gap_pct", 0.15))
        if gap_pct >= minimum and last.close < last.open:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.56, "Gap up is being faded", "Gap", str(minimum), f"gap_pct={gap_pct:.3f}")
        if gap_pct <= -minimum and last.close > last.open:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.56, "Gap down is being faded", "Gap", str(minimum), f"gap_pct={gap_pct:.3f}")
        return _hold(self.key, snapshot, "No gap fade", "Gap", str(minimum), f"gap_pct={gap_pct:.3f}")


class AlligatorStrategy:
    key: ClassVar[str] = "alligator"
    name: ClassVar[str] = "Alligator"
    category: ClassVar[str] = "trend"
    description: ClassVar[str] = "Williams Alligator lips, teeth, and jaw are stacked. Averages use their published shifts."
    default_params: ClassVar[dict[str, Any]] = {"jaw": 13, "teeth": 8, "lips": 5, "jaw_shift": 8, "teeth_shift": 5, "lips_shift": 3}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "jaw", 13, 5)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        jaw_n = int(_param(snapshot.params, "jaw", 13))
        teeth_n = int(_param(snapshot.params, "teeth", 8))
        lips_n = int(_param(snapshot.params, "lips", 5))
        jaw_shift = int(_param(snapshot.params, "jaw_shift", 8))
        teeth_shift = int(_param(snapshot.params, "teeth_shift", 5))
        lips_shift = int(_param(snapshot.params, "lips_shift", 3))
        closes = [bar.close for bar in snapshot.bars]
        need = jaw_n + jaw_shift
        if len(closes) < need:
            return _hold(self.key, snapshot, "Insufficient bars for Alligator", "Alligator", str(need))
        jaw_line = sma(closes, jaw_n)
        teeth_line = sma(closes, teeth_n)
        lips_line = sma(closes, lips_n)
        jaw = jaw_line[-1 - jaw_shift]
        teeth = teeth_line[-1 - teeth_shift]
        lips = lips_line[-1 - lips_shift]
        if jaw is None or teeth is None or lips is None:
            return _hold(self.key, snapshot, "Alligator averages are not ready", "Alligator", str(need))
        if lips > teeth > jaw:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.62, "Alligator is stacked upward", "Alligator", f"{lips_n}/{teeth_n}/{jaw_n}", f"lips={lips:.5f}")
        if lips < teeth < jaw:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.62, "Alligator is stacked downward", "Alligator", f"{lips_n}/{teeth_n}/{jaw_n}", f"lips={lips:.5f}")
        return _hold(self.key, snapshot, "Alligator lines are tangled", "Alligator", f"{lips_n}/{teeth_n}/{jaw_n}")


class VwapReversionStrategy:
    key: ClassVar[str] = "vwap_reversion"
    name: ClassVar[str] = "VWAP Reversion"
    category: ClassVar[str] = "mean_reversion"
    description: ClassVar[str] = "Close is stretched from volume-weighted average price. HOLD when volume is missing."
    default_params: ClassVar[dict[str, Any]] = {"period": 20, "threshold_pct": 0.3}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 20, 5)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        if not _has_volume(snapshot.bars):
            return _hold(self.key, snapshot, "Volume was not supplied", "VWAP", "volume")
        period = int(_param(snapshot.params, "period", 20))
        threshold = float(_param(snapshot.params, "threshold_pct", 0.3))
        window = snapshot.bars[-period:]
        if len(window) < period:
            return _hold(self.key, snapshot, "Insufficient bars for VWAP", "VWAP", str(period))
        volume = sum(bar.volume for bar in window)
        if volume <= 0:
            return _hold(self.key, snapshot, "Volume was not supplied", "VWAP", "volume")
        typical = sum(((bar.high + bar.low + bar.close) / 3) * bar.volume for bar in window) / volume
        if typical == 0:
            return _hold(self.key, snapshot, "VWAP is zero", "VWAP", str(period))
        distance = (window[-1].close - typical) / abs(typical) * 100
        if distance <= -threshold:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.58, "Close is below VWAP", "VWAP", str(threshold), f"distance={distance:.3f}%")
        if distance >= threshold:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.58, "Close is above VWAP", "VWAP", str(threshold), f"distance={distance:.3f}%")
        return _hold(self.key, snapshot, "Close is near VWAP", "VWAP", str(threshold), f"distance={distance:.3f}%")


class ObvTrendStrategy:
    key: ClassVar[str] = "obv_trend"
    name: ClassVar[str] = "OBV Trend"
    category: ClassVar[str] = "volume"
    description: ClassVar[str] = "On-balance volume and close slope agree. HOLD when volume is missing."
    default_params: ClassVar[dict[str, Any]] = {"period": 20}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 20, 5)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        if not _has_volume(snapshot.bars):
            return _hold(self.key, snapshot, "Volume was not supplied", "OBV", "volume")
        period = int(_param(snapshot.params, "period", 20))
        bars = snapshot.bars
        if len(bars) < period + 1:
            return _hold(self.key, snapshot, "Insufficient bars for OBV", "OBV", str(period))
        obv = 0.0
        series: list[float] = [0.0]
        for i in range(1, len(bars)):
            if bars[i].close > bars[i - 1].close:
                obv += bars[i].volume
            elif bars[i].close < bars[i - 1].close:
                obv -= bars[i].volume
            series.append(obv)
        obv_slope = series[-1] - series[-1 - period]
        price_slope = bars[-1].close - bars[-1 - period].close
        if obv_slope > 0 and price_slope > 0:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.58, "OBV and price are rising", "OBV", str(period), f"obv_slope={obv_slope:.2f}")
        if obv_slope < 0 and price_slope < 0:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.58, "OBV and price are falling", "OBV", str(period), f"obv_slope={obv_slope:.2f}")
        return _hold(self.key, snapshot, "OBV and price disagree", "OBV", str(period), f"obv_slope={obv_slope:.2f}")


class LiquiditySweepStrategy:
    key: ClassVar[str] = "liquidity_sweep"
    name: ClassVar[str] = "Liquidity Sweep"
    category: ClassVar[str] = "price_action"
    description: ClassVar[str] = "The latest wick takes the prior swing high or low and the close returns inside it."
    default_params: ClassVar[dict[str, Any]] = {"period": 20}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "period", 20, 5)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        period = int(_param(snapshot.params, "period", 20))
        bars = snapshot.bars
        if len(bars) < period + 1:
            return _hold(self.key, snapshot, "Insufficient bars for a swing sweep", "Sweep", f"need>={period + 1}")
        prior = bars[-(period + 1) : -1]
        swing_high = max(bar.high for bar in prior)
        swing_low = min(bar.low for bar in prior)
        last = bars[-1]
        if last.high > swing_high and last.close < swing_high:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.6, "Wick swept the prior high and close returned inside", "Sweep", str(period), f"high={swing_high:.5f}")
        if last.low < swing_low and last.close > swing_low:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.6, "Wick swept the prior low and close returned inside", "Sweep", str(period), f"low={swing_low:.5f}")
        return _hold(self.key, snapshot, "No swing sweep and return", "Sweep", str(period))


class FairValueGapStrategy:
    key: ClassVar[str] = "fvg"
    name: ClassVar[str] = "Fair Value Gap"
    category: ClassVar[str] = "price_action"
    description: ClassVar[str] = "A three-candle price gap, with the latest close still on the gap side."
    default_params: ClassVar[dict[str, Any]] = {}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        if len(snapshot.bars) < 3:
            return _hold(self.key, snapshot, "Need three candles for a gap", "FVG", "3")
        first, _middle, last = snapshot.bars[-3:]
        if first.high < last.low:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.58, "Bullish three-candle gap remains open", "FVG", "gap", f"gap={first.high:.5f}/{last.low:.5f}")
        if first.low > last.high:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.58, "Bearish three-candle gap remains open", "FVG", "gap", f"gap={last.high:.5f}/{first.low:.5f}")
        return _hold(self.key, snapshot, "The last three candles do not leave a gap", "FVG", "gap")


class OrderBlockStrategy:
    key: ClassVar[str] = "order_block"
    name: ClassVar[str] = "Order Block"
    category: ClassVar[str] = "price_action"
    description: ClassVar[str] = "Price retests the last opposite candle before a directional close impulse."
    default_params: ClassVar[dict[str, Any]] = {"impulse_bars": 3}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return _period_ok(params, "impulse_bars", 3, 2)

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        impulse = int(_param(snapshot.params, "impulse_bars", 3))
        bars = snapshot.bars
        if len(bars) < impulse + 2:
            return _hold(self.key, snapshot, "Insufficient bars for an order-block retest", "Order block", str(impulse))
        last = bars[-1]
        start = bars[-1 - impulse]
        bullish_impulse = last.close > start.close and last.close > last.open
        bearish_impulse = last.close < start.close and last.close < last.open
        opposite = None
        for bar in reversed(bars[-1 - impulse : -1]):
            if bullish_impulse and bar.close < bar.open:
                opposite = bar
                break
            if bearish_impulse and bar.close > bar.open:
                opposite = bar
                break
        if opposite is None:
            return _hold(self.key, snapshot, "No opposite candle before the impulse", "Order block", str(impulse))
        if bullish_impulse and opposite.low <= last.low <= opposite.high and last.close > opposite.high:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.58, "Close reclaimed a bullish order-block candle", "Order block", str(impulse), f"block={opposite.low:.5f}/{opposite.high:.5f}")
        if bearish_impulse and opposite.low <= last.high <= opposite.high and last.close < opposite.low:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.58, "Close rejected a bearish order-block candle", "Order block", str(impulse), f"block={opposite.low:.5f}/{opposite.high:.5f}")
        return _hold(self.key, snapshot, "Price is not retesting the opposite candle", "Order block", str(impulse))


class SessionBreakoutStrategy:
    key: ClassVar[str] = "session_breakout"
    name: ClassVar[str] = "Session Breakout"
    category: ClassVar[str] = "breakout"
    description: ClassVar[str] = "Close breaks the high or low of bars in the configured UTC hour window. HOLD when bar time is missing."
    default_params: ClassVar[dict[str, Any]] = {"start_hour": 7, "end_hour": 16}

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        start = int(_param(params, "start_hour", 7))
        end = int(_param(params, "end_hour", 16))
        if not (0 <= start <= 23 and 0 <= end <= 23 and start != end):
            return False, ("start_hour and end_hour must be different hours from 0 to 23",)
        return True, ()

    def evaluate(self, snapshot: StrategySnapshot) -> StrategyIntention:
        start = int(_param(snapshot.params, "start_hour", 7))
        end = int(_param(snapshot.params, "end_hour", 16))
        stamped = [(bar, _hour(bar.time)) for bar in snapshot.bars]
        if any(hour is None for _bar, hour in stamped):
            return _hold(self.key, snapshot, "Bar time was not supplied", "Session", f"{start}-{end}")

        def in_window(hour: int) -> bool:
            if start < end:
                return start <= hour < end
            return hour >= start or hour < end

        window = [bar for bar, hour in stamped[:-1] if hour is not None and in_window(hour)]
        if not window:
            return _hold(self.key, snapshot, "No earlier bars in the session window", "Session", f"{start}-{end}")
        ceiling = max(bar.high for bar in window)
        floor = min(bar.low for bar in window)
        close = snapshot.bars[-1].close
        if close > ceiling:
            return _go(self.key, snapshot, EngineSignalAction.BUY, 0.6, "Close broke the session high", "Session", f"{start}-{end}", f"close={close:.5f}; high={ceiling:.5f}")
        if close < floor:
            return _go(self.key, snapshot, EngineSignalAction.SELL, 0.6, "Close broke the session low", "Session", f"{start}-{end}", f"close={close:.5f}; low={floor:.5f}")
        return _hold(self.key, snapshot, "No session-range break", "Session", f"{start}-{end}", f"close={close:.5f}")


def library_plugins() -> list[Any]:
    return [
        DonchianBreakoutStrategy(),
        StochasticStrategy(),
        CciStrategy(),
        WilliamsRStrategy(),
        AdxTrendStrategy(),
        SupertrendStrategy(),
        KeltnerChannelStrategy(),
        TripleEmaStrategy(),
        HullTrendStrategy(),
        AroonStrategy(),
        AwesomeOscillatorStrategy(),
        EngulfingStrategy(),
        PinBarStrategy(),
        InsideBarBreakoutStrategy(),
        RsiPullbackStrategy(),
        BollingerSqueezeStrategy(),
        IchimokuStrategy(),
        HeikinAshiTrendStrategy(),
        LinearRegressionStrategy(),
        ZScoreReversionStrategy(),
        Nr7BreakoutStrategy(),
        ThreeBarReversalStrategy(),
        GapFillStrategy(),
        AlligatorStrategy(),
        VwapReversionStrategy(),
        ObvTrendStrategy(),
        LiquiditySweepStrategy(),
        FairValueGapStrategy(),
        OrderBlockStrategy(),
        SessionBreakoutStrategy(),
    ]
